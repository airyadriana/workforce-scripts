# -*- coding: UTF-8 -*-
"""
   Copyright 2018 Esri

   Licensed under the Apache License, Version 2.0 (the "License");

   you may not use this file except in compliance with the License.

   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software

   distributed under the License is distributed on an "AS IS" BASIS,

   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

   See the License for the specific language governing permissions and

   limitations under the License.​

   This sample creates assignments from CSV files
"""


import pandas as pd
import argparse
import csv
import logging
import logging.handlers
import traceback
import sys
import arrow
import dateutil
import types
from arcgis.apps import workforce
from arcgis.gis import GIS
from datetime import datetime, timedelta

def uploadAssignments_workforce():
    def log_critical_and_raise_exception(message):
        logging.getLogger().critical(message)
        raise Exception(message)

    def initialize_logging(log_file):
        """
        Setup logging
        :param log_file: (string) The file to log to
        :return: (Logger) a logging instance
        """
        # initialize logging
        formatter = logging.Formatter("[%(asctime)s] [%(filename)30s:%(lineno)4s - %(funcName)30s()]\
                 [%(threadName)5s] [%(name)10.10s] [%(levelname)8s] %(message)s")
        # Grab the root logger
        logger = logging.getLogger()
        # Set the root logger logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logger.setLevel(logging.DEBUG)
        # Create a handler to print to the console
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        sh.setLevel(logging.INFO)
        # Create a handler to log to the specified file
        rh = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=10485760)
        rh.setFormatter(formatter)
        rh.setLevel(logging.DEBUG)
        # Add the handlers to the root logger
        logger.addHandler(sh)
        logger.addHandler(rh)
        return logger

    def main(arguments):
        # initialize logging
        logger = initialize_logging(arguments.log_file)
        # Create the GIS
        logger.info("Authenticating...")
        # First step is to get authenticate and get a valid token
        gis = GIS(arguments.org_url,
                  username=arguments.username,
                  password=arguments.password,
                  verify_cert=not arguments.skip_ssl_verification)
        # Get the project and data
        item = gis.content.get(arguments.project_id)
        project = workforce.Project(item)
        dispatcher = project.dispatchers.search(
            where="{}='{}'".format(project._dispatcher_schema.user_id, arguments.username))
        if not dispatcher:
            log_critical_and_raise_exception("{} is not a dispatcher".format(args.username))
        # Read the csv file
        logger.info("Reading CSV file: {}...".format(arguments.csv_file))
        assignments_in_csv = []
        with open(arguments.csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                assignments_in_csv.append(row)
        #########################################
        #GET A LIST OF THE CSV'S WORK_ORDER_IDS##
        #########################################
        assignments_in_csv_workOrderId =[] #creates an empty list to save the order IDs
        for i in assignments_in_csv:
            orderID = i['Work Order Id'] #A work order ID in the CSV file we want to load
            assignments_in_csv_workOrderId.append(orderID) #append the order IDs
        ####################################################
        #GET THE LAST 30 DAYS WORK ORDERS WITHIN WORKFORCE###
        #####################################################

        today = datetime.today() #time stamp at the moment of runnig this script
        thirtyDays_ago = today - timedelta(days=30) #obtain the date and time from 30 days ago

        lastThirtyDays ="{} <= '{}' OR {} >= '{}'"\
            .format(project._track_schema.creation_date, today.strftime("%m/%d/%Y %H:%M:%S"),
                    project._track_schema.creation_date, thirtyDays_ago.strftime("%m/%d/%Y %H:%M:%S"))#create a query of the last 30 days
        assgments = project.assignments.search(where=lastThirtyDays) #list all the assignments within Workforce Web App
        currentOrders = [] #create an empty list where we will save the assignments withing Workforce
        for a in range(0,len(assgments)):
            assgment = assgments[a]
            assgment_orderID = assgment.work_order_id
            currentOrders.append(assgment_orderID)
        ################################################################
        ###COMPARE THE CSV'S ORDER IDs TO THE CURRENT WORKORDER #########
        ###IN WORKFORCE AND GENERATE A LIST OF DUPLICATES###############
        ##############################################################
        duplicates = [] #list containing the CSV's workorder that are identical to those in workforce
        for order in assignments_in_csv_workOrderId:
            for current_o in currentOrders:
                if order == current_o:
                    duplicates.append(order)
        #########################################################
        ##DROP THE DUPLICATES FROM THE ASSIGNMENTS IN THE CSV####
        #########################################################

        for i in reversed(range(len(assignments_in_csv))):
            a = assignments_in_csv[i]
            orderID = a['Work Order Id']
            for h in duplicates:
                if orderID == h:
                    assignments_in_csv.pop(i)

        #############################################################
        #######UPLOAD NON-REPEATED OR INFORM THAT ALL ARE REPEATED###
        #############################################################

        if len(assignments_in_csv) == 0:
            print("The assignments you are trying to upload were previously uploaded. This scrip "
                  "won't run to prevent duplicate work order IDs.")
        elif len(assignments_in_csv) > 0:
            # Fetch assignment types
            assignment_types = project.assignment_types.search()
            assignment_type_dict = {}
            for assignment_type in assignment_types:
                assignment_type_dict[assignment_type.name] = assignment_type

            # Fetch dispatchers
            dispatchers = project.dispatchers.search()
            dispatchers_dict = {}
            for dispatcher in dispatchers:
                dispatchers_dict[dispatcher.user_id] = dispatcher

            # Fetch the workers
            workers = project.workers.search()
            workers_dict = {}
            for worker in workers:
                workers_dict[worker.user_id] = worker

            # assignments to add
            assignments_to_add = []
            for assignment in assignments_in_csv:
                assignment_to_add = workforce.Assignment(project,
                                                         assignment_type=assignment_type_dict[
                                                             assignment[args.assignment_type_field]],
                                                         )

                # Create the geometry
                geometry = dict(x=float(assignment[args.x_field]),
                                y=float(assignment[args.y_field]),
                                spatialReference=dict(
                                    wkid=int(args.wkid)))
                assignment_to_add.geometry = geometry

                # Determine the assignment due date, and if no time is provided, make the due date all day
                if args.due_date_field and assignment[args.due_date_field]:
                    d = arrow.Arrow.strptime(assignment[args.due_date_field], args.date_format).replace(
                        tzinfo=dateutil.tz.gettz(args.timezone))
                    if d.datetime.second == 0 and d.datetime.hour == 0 and d.datetime.minute == 0:
                        d = d.replace(hour=23, minute=59, second=59)
                    # Convert date to UTC time
                    assignment_to_add.due_date = d.to('utc').datetime

                # Set the location
                assignment_to_add.location = assignment[args.location_field]

                # Set the dispatcher
                if args.dispatcher_field and assignment[args.dispatcher_field]:
                    assignment_to_add.dispatcher = dispatchers_dict[assignment[args.dispatcher_field]]
                else:
                    assignment_to_add.dispatcher = dispatcher

                # Fetch workers and assign the worker to the assignment
                if args.worker_field and assignment[args.worker_field]:
                    assignment_to_add.worker = workers_dict[assignment[args.worker_field]]
                    assignment_to_add.assigned_date = arrow.now().to('utc').datetime
                    assignment_to_add.status = "assigned"
                else:
                    assignment_to_add.status = "unassigned"

                # Set the priority
                if args.priority_field and assignment[args.priority_field]:
                    assignment_to_add.priority = assignment[args.priority_field]

                # Set the description
                if args.description_field and assignment[args.description_field]:
                    assignment_to_add.description = assignment[args.description_field]

                # Set the work order id
                if args.work_order_id_field and assignment[args.work_order_id_field]:
                    assignment_to_add.work_order_id = assignment[args.work_order_id_field]

                # Set attachment
                if args.attachment_file_field and assignment[args.attachment_file_field]:
                    assignment_to_add.attachment_file = types.SimpleNamespace()
                    assignment_to_add.attachment_file = assignment[args.attachment_file_field]

                # Add all assignments to the list created
                assignments_to_add.append(assignment_to_add)

            # Batch add all assignments to the project
            logger.info("Adding Assignments...")
            assignments = project.assignments.batch_add(assignments_to_add) #I NEED TO UNCOMMENT THI TO WORK
            logger.info("Adding Attachments...")
            for assignment in assignments:
                if hasattr(assignment, "attachment_file"):
                    assignment.attachments.add(assignment.attachment_file)
            logger.info("Completed")

            if len(duplicates) == 0:
                print("SUCCESS!!")
            elif len(duplicates) > 0:
                print("This work orders were previously uploaded and they were ignored to prevent duplication:")
                print(duplicates)
                print("The rest of the work orders have been uploaded successfully.")

    def rawCSV_toGoodCSV():

        #get the path
        path = str(input("Input the path of the csv file:")) #'C:\Users\PR_PERALTA\Downloads\report.csv'
        #formattedPath = path.replace('\\', "/")
        #print(formattedPath)

        #read the file
        file = pd.read_csv(path)

        #split the location coordinates column and input them in the same dtaframe
        file[['xField','yField']] = file['Location Coordinates'].str.split(',', expand=True)

        #drop the Location Coordinates column
        d = file.drop(columns="Location Coordinates")

        #rename columns
        header_names = ["Work Order Id","Type","Due Date","Description","Location","xField",
                        "yField"]
        d.columns = header_names

        #formatting the date data
        l = len(d.index)
        times = ["00:00:01"]* l
        d["times"] =times
        dueDate = d["Due Date"] + " " + d["times"]
        d["Due Date"] = dueDate

        dateFormat = pd.to_datetime(d["Due Date"], format= "%m/%d/%Y %H:%M:%S")
        d["Due Date"] = dateFormat
        d["Due Date"] =d["Due Date"].dt.strftime("%m/%d/%Y %H:%M:%S")



        #save to CSV
        d.to_csv(r"C:\Users\PR_PERALTA\Downloads\Formatted_report.csv",) #needs to be changed for each user

    rawCSV_toGoodCSV()

    if __name__ == "__main__":
        # Get all of the commandline arguments
        parser = argparse.ArgumentParser("Add Assignments to Workforce Project")
        parser.add_argument('-u', dest='username', help="The username to authenticate with", required=True)
        parser.add_argument('-p', dest='password', help="The password to authenticate with", required=True)
        parser.add_argument('-org', dest='org_url', help="The url of the org/portal to use", required=True)
        # Parameters for workforce
        parser.add_argument('-project-id', dest='project_id', help="The id of the project to add assignments to",
                            required=True)
        parser.add_argument('-x-field', dest='x_field', help="The field that contains the x SHAPE information",
                            required=True)
        parser.add_argument('-y-field', dest='y_field', help="The field that contains the y SHAPE information",
                            required=True)
        parser.add_argument('-assignment-type-field', dest='assignment_type_field',
                            help="The field that contains the assignmentType", required=True)
        parser.add_argument('-location-field', dest='location_field',
                            help="The field that contains the location", required=True)
        parser.add_argument('-dispatcher-field', dest='dispatcher_field',
                            help="The field that contains the dispatcherId")
        parser.add_argument('-description-field', dest='description_field',
                            help="The field that contains the description")
        parser.add_argument('-priority-field', dest='priority_field', help="The field that contains the priority")
        parser.add_argument('-work-order-id-field', dest='work_order_id_field',
                            help="The field that contains the workOrderId")
        parser.add_argument('-due-date-field', dest='due_date_field', help="The field that contains the dispatcherId")
        parser.add_argument('-worker-field', dest='worker_field', help="The field that contains the workers username")
        parser.add_argument('-attachment-file-field', dest='attachment_file_field',
                            help="The field that contains the file path to the attachment to upload")
        parser.add_argument('-date-format', dest='date_format', default="%m/%d/%Y %H:%M:%S",
                            help="The format to use for the date (eg. '%m/%d/%Y %H:%M:%S')")
        parser.add_argument('-timezone', dest='timezone', default="UTC", help="The timezone for the assignments")
        parser.add_argument('-csv-file', dest='csv_file', help="The path/name of the csv file to read")
        parser.add_argument('-wkid', dest='wkid', help='The wkid that the x,y values are use', type=int, default=4326)
        parser.add_argument('-log-file', dest='log_file', help='The log file to use', required=True)
        parser.add_argument('--skip-ssl-verification', dest='skip_ssl_verification', action='store_true',
                            help="Verify the SSL Certificate of the server")
        args = parser.parse_args()
        try:
            main(args)
        except Exception as e:
            logging.getLogger().critical("Exception detected, script exiting")
            logging.getLogger().critical(e)
            logging.getLogger().critical(traceback.format_exc().replace("\n", " | "))

uploadAssignments_workforce()