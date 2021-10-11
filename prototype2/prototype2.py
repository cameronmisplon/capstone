import sys
import os
import random
import threading
import subprocess
import mysql.connector
import numpy as np
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.optimize import minimize
from pymoo.factory import get_sampling
from multiprocessing.pool import ThreadPool
from pymoo.core.problem import starmap_parallelized_eval
from pymoo.core.problem import ElementwiseProblem
from threading import *

## starting mysql server
os.system("service mysql start")

## reading in arguments

wcard_name = sys.argv[1]
solver_runtime = int(sys.argv[2])*1000

##creating semaphore for writing to database

lock = Semaphore(1)

## creating database

mydb = mysql.connector.connect(host="localhost",user="root",password="")
mycursor = mydb.cursor()
mycursor.execute("CREATE DATABASE ancestrydb")
mydb.close()
ancestrydb = mysql.connector.connect(host="localhost",user="root",password="",database="ancestrydb")
mycursor = ancestrydb.cursor()
mycursor.execute("CREATE TABLE states (previous INT, current INT, a INT, b INT, c INT, e INT, f INT, r INT, x INT, endscore INT, improvement INT, stucktime INT)")
sql = "INSERT INTO states (previous, current, a, b, c, e, f, r, x, endscore, improvement, stucktime) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

##parallelization

n_threads= 6
pool = ThreadPool(n_threads)
threadid =0

#valid parameters stored in arrays (in order they need to be supplied)

parameter_a = [1,2,5, 12, 17, 25, 50, 100,113, 125, 150, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
parameter_b = [1,2,3,5,10,12,25,50,100,125,150,200,300,400,500,600,700,800,900,1000]
parameter_c =[10,50,100,500,1000,3000,7000,10000,25000,50000,100000,200000,300000,400000,500000,600000,700000,800000,900000,1000000]
parameter_e = [0.1,0.5,1,2,5,10,25,50,75,100,150,200,300,400,500,600,700,800,900,1000]
parameter_f = [0.1,0.2,0.5,0.75,1,5,10,25,50,100,150,200,300,400,500,600,700,800,900,1000]
parameter_r = [0,1,2,3,5,10,12,15,20,25,30,40,50,60,70,75,80,90,95,100]
parameter_x = [1,2,5,10,50,100,150,250,500,750,1000,2000,3000,4000,5000,6000,7000,8000,9000,10000]
end_scores = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
improvement = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
stuck_time = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]


#Defining problem class
class BestScore(ElementwiseProblem):

    def __init__(self, **kwargs):
        super().__init__(n_var=10,n_obj=1,n_constr=0,xl=0,xu=19,**kwargs)
    def _evaluate(self,x, out,*args, **kwargs):
        global end_scores
        global improvement
        global stuck_time
        global threadid
        if (end_scores[x[7]]+improvement[x[8]]+stuck_time[x[9]]==0):  #first generation run of carlsat, implies no previous saved states
            lock.acquire()
            threadid+=1
            identity = threadid
            lock.release()
            statefilename = "./mnt/ramdisk/state"+str(identity)+".out"
            path = f"./CarlSAT -a {parameter_a[x[0]]} -b {parameter_b[x[1]]} -c {parameter_c[x[2]]} -e {parameter_e[x[3]]} -f {parameter_f[x[4]]} -r {parameter_r[x[5]]} -x {parameter_x[x[6]]} -m {solver_runtime/20} -v 2 -z {wcard_name} -w {statefilename}" 
            result = subprocess.Popen(path, stdout=subprocess.PIPE,shell=True)
            output = result.communicate()[0].splitlines()
            cost =0
            stuck =solver_runtime/20
            for i in range(len(output)-1,-1,-1):
                line = str(output[i])
                if (line.find("after") != -1):
                    temp = line[line.find(")")+5::]
                    cost = int(temp[0:temp.find(" ")].replace(",",""))
                    break
                elif (line.find("Time")!=-1):
                    temp = line[line.find(":")+2::]
                    timetaken = float(temp[0:temp.find(" ")])*1000
                    stuck-=timetaken     
            
            val = (0, identity, parameter_a[x[0]], parameter_b[x[1]], parameter_c[x[2]], parameter_e[x[3]], parameter_f[x[4]], parameter_r[x[5]], parameter_x[x[6]],cost,0,stuck)
            lock.acquire()
            mycursor.execute(sql,val)
            ancestrydb.commit()
            lock.release()
            
            min_valid=[100000000,100000000,100000000]
            max_valid=[0,0,0]
            if (identity%50==0):
                mycursor.execute("SELECT current, endscore, improvement, stucktime FROM states")
                myresult = mycursor.fetchall()
                for k in range(0,len(myresult),1):
                    min_valid[0] = min(min_valid[0],myresult[k][1])
                    min_valid[1] = min(min_valid[1],myresult[k][2])
                    min_valid[2] = min(min_valid[2],myresult[k][3])
                    max_valid[0] = max(max_valid[0],myresult[k][1])
                    max_valid[1] = max(max_valid[1],myresult[k][2])
                    max_valid[2] = max(max_valid[2],myresult[k][3])
                end_scores = ([random.choice(range(min_valid[0],max_valid[0]+1)) for t in range(20)])
                improvement = ([random.choice(range(min_valid[1],max_valid[1]+1)) for u in range(20)])
                stuck_time = ([random.choice(range(min_valid[2],max_valid[2]+1)) for v in range(20)])
                end_scores.sort()
                improvement.sort(reverse=True)
                stuck_time.sort()
            
            out["F"] = [cost]
        else:
            lock.acquire()
            mycursor.execute("SELECT current, endscore, improvement, stucktime FROM states")
            myresult = mycursor.fetchall()
            threadid+=1
            identity = threadid
            lock.release()
            number_of_previous_generations=0
            excess = 0
            while(True):
                if (myresult[len(myresult)-1-excess][0] % 50 ==0):
                    number_of_previous_generations = (len(myresult)-excess)//50
                    break
                excess+=1
            closest_matching_state_file =0
            min_D = 100000000
            for j in range(0,number_of_previous_generations*50,1):
                D = ((end_scores[x[7]]-myresult[j][1])**2)+((improvement[x[8]]-myresult[j][2])**2)+(((stuck_time[x[9]]-myresult[j][3])**2)*0.5)
                min_D = min(min_D,D)
                if (D == min_D):
                    closest_matching_state_file =j+1
            
            closest_state = "./mnt/ramdisk/state"+str(closest_matching_state_file)+".out"
            statefilename = "./mnt/ramdisk/state"+str(identity)+".out"
            path = f"./CarlSAT -a {parameter_a[x[0]]} -b {parameter_b[x[1]]} -c {parameter_c[x[2]]} -e {parameter_e[x[3]]} -f {parameter_f[x[4]]} -r {parameter_r[x[5]]} -x {parameter_x[x[6]]} -m {solver_runtime/20} -v 2 -z {wcard_name} -i {closest_state} -w {statefilename}" 
            result = subprocess.Popen(path, stdout=subprocess.PIPE,shell=True)
            output = result.communicate()[0].splitlines()
            cost = 0
            stuck =solver_runtime/20
            for i in range(len(output)-1,-1,-1):
                line = str(output[i])
                if (line.find("after") != -1):
                    temp = line[line.find(")")+5::]
                    cost = int(temp[0:temp.find(" ")].replace(",",""))
                    break
                elif (line.find("Time")!=-1):
                    temp = line[line.find(":")+2::]
                    timetaken = float(temp[0:temp.find(" ")])*1000
                    stuck-=timetaken    
            score_improvement = myresult[j][1]-cost  
            
            val = (closest_matching_state_file, identity, parameter_a[x[0]], parameter_b[x[1]], parameter_c[x[2]], parameter_e[x[3]], parameter_f[x[4]], parameter_r[x[5]], parameter_x[x[6]],cost,score_improvement,stuck)  
            lock.acquire()
            mycursor.execute(sql,val)
            ancestrydb.commit()
            lock.release()
            
            min_valid=[100000000,100000000,100000000]
            max_valid=[0,0,0]
            if (identity%50==0):
                for k in range(0,len(myresult),1):
                    min_valid[0] = min(min_valid[0],myresult[k][1])
                    min_valid[1] = min(min_valid[1],myresult[k][2])
                    min_valid[2] = min(min_valid[2],myresult[k][3])
                    max_valid[0] = max(max_valid[0],myresult[k][1])
                    max_valid[1] = max(max_valid[1],myresult[k][2])
                    max_valid[2] = max(max_valid[2],myresult[k][3])
                end_scores = ([random.choice(range(min_valid[0],max_valid[0]+1)) for t in range(20)])
                improvement = ([random.choice(range(min_valid[1],max_valid[1]+1)) for u in range(20)])
                stuck_time = ([random.choice(range(min_valid[2],max_valid[2]+1)) for v in range(20)])
                end_scores.sort()
                improvement.sort()
                stuck_time.sort()
            
            out["F"] = [cost]
            
            
        	##first need to choose a state file that most closely matches the values of end_score, improvement and stuck time that the ga chooses. This is done by looping through every row in the database and maintaining a running counter of the row with the closest match.
        	##once we have chosen a state file we run exactly the same lines of code as the if block except that we add an additional -i paramater to the path variable for the chosen state, and where cost and stucktime is calculated we also calculate the improvement in score.
#defining DE algorithm
problem = BestScore(runner=pool.starmap, func_eval=starmap_parallelized_eval)
algorithm = DE(pop_size=50,sampling=get_sampling("int_random"))
res = minimize(problem,algorithm,("n_gen",20),verbose=True,seed=1)

##querying the database
mycursor.execute("SELECT * FROM states")
myresult = mycursor.fetchall()

##output results and parameters to text file
text_file = open("output.txt","w")
for row in myresult:
    text_file.write(str(row))
    text_file.write("\n")
text_file.close()

## closing/deleting the database
mycursor.execute("DROP DATABASE ancestrydb")
mycursor.close()
ancestrydb.close()

