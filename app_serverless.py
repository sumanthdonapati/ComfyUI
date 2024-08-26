from flux_lora import flux_train
from utilities import *
import argparse
from glob import glob
import os
import boto3
from botocore.exceptions import NoCredentialsError
from tqdm import tqdm
from boto3.s3.transfer import TransferConfig
from pathlib import Path
import shutil
import csv
import re
import json
import requests
import os
import time
import traceback
import runpod
# os.environ["CUDA_VISIBLE_DEVICES"] = "0"

machine = os.environ["machine_type"]

def run_flux_train(job):
    # new_message = receive_message()
    # delete_message(new_message)
    input_json = job["input"] #json.loads(new_message['Body'])
    request_id = input_json["request_id"]
    machine_type = input_json["machine_type"]
    theme = input_json["theme"].lower()
    print("input json:",input_json)
    queue_status = f'https://api.spotstage.segmind.com/finetune/request/{request_id}/status'
    queue_response = requests.request("GET", queue_status, headers=headers)
    print("status:",queue_response.text)
    q_val = queue_response.json()
    
    if q_val['status'] == "AVAILABLE":
        print("Status Available, deleting from the queue")
        # delete_message(new_message)
        
    # if q_val['status'] not in ["QUEUED","RETRIED"]:
    #     # print('raise error')
    #     raise Exception('not queued')

    print("theme: ",theme)
    if theme not in ["flux"]:
        print('not flux theme')
        time.sleep(10)
        raise Exception('Not Flux request')
        
    print('machine type: ',machine_type)
    if machine_type != machine:
        print('raise error')
        raise Exception('Incorrect Machine Type')
    print("recieved msg")
    print('queue response:',q_val)
    print(input_json)
    try:
        model_metadata, training_metadata, cloud_storage_url, output_image_url = flux_train(input_json)
        payload = {"status":"TRAINING_COMPLETED","request_id":request_id,"cloud_storage_url":cloud_storage_url,"output_image_url":output_image_url,"model_metadata":json.dumps(model_metadata),"training_metadata":json.dumps(training_metadata),"machine_type":machine}
        print('payload:',payload)
        response = requests.request("POST", status_url, headers=headers, json=payload)
        # delete_message(new_message)
        try:
            for i in range(1):
                if response.status_code != 200:
                    time.sleep(1)
                    response = requests.request("POST", status_url, headers=headers, json=payload)
        except:
            pass
        print(response.status_code)
        print(response.text)
    except Exception as e:
        print("trace back:",str(traceback.format_exc()))
        print('failed',e)
        if "FileNotFoundError" in str(e):
            e = "Download failed"
            
        if "CUDA out of memory" in str(e):
            e = "GPU overloaded, try with smaller dataset"
        
        if "empty dataset" in str(e):
            e = "Looks like empty dataset. Please do not create subfolders, only zip the images"
        else:
            try:
                print(str(e))
                with open('logs.txt', 'a') as file:
                    file.write("input: "+str(input_json)+"\n")
                    file.write("error:"+str(e)+"\n")
                    file.write("--------------"+"\n")
                e = "Internal Server Error"
            except:
                e = "Internal Server Error"
                
        payload = {"status":"FAILED","error_message":e,"request_id":request_id,"machine_type":machine}
        print(payload)
        response = requests.request("POST", status_url, headers=headers, json=payload)
        # delete_message(new_message)
        try:
            for i in range(3):
                if response.status_code != 200:
                    time.sleep(45)
                    response = requests.request("POST", status_url, headers=headers, json=payload)
        except:
            pass
        print(response.status_code)
        print(response.text)


print("running serverless")
runpod.serverless.start({"handler": run_flux_train})
