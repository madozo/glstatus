import os
import sys
import subprocess
import re
import requests
import json
from tabulate import tabulate
import time


def cmd(command):
    args = command.split()
    result = subprocess.run(args, stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8').rstrip()

def color_coded(status):
    if status == "success":
        return f'\033[92m{status}\033[0m'
    elif status == "running":
        return f'\033[94m{status}\033[0m'
    elif status == "failed":
        return f'\033[91m{status}\033[0m'
    elif status in ("skipped", "manual"):
        return f'\033[90m{status}\033[0m'
    elif status == "created":
        return status
    else:
        return f'\033[93m{status}\033[0m'

class Result:
    def __init__(self):
        self.job_header = ["name", "status", "stage", "duration", "url"]
        self.pl_data = []
        self.job_data = []

    def add_job_data(self, job_data):
        self.job_data.append(job_data)

    def add_pipeline_data(self, pl_data):
        self.pl_data = pl_data

    def get_pl_table(self):
        return tabulate(self.pl_data, tablefmt="psql")

    def get_job_table(self):
        return tabulate(self.job_data, headers=self.job_header, tablefmt="psql")

    def print_tables(self):
        print("Current pipeline")
        print(self.get_pl_table())
        print("Jobs")
        print(self.get_job_table())

def read_gl_token():
    token = os.environ.get('GITLAB_API_PRIVATE_TOKEN')
    if token is None or len(token) == 0:
        print("Gitlab private token is not set. Please 'export GITLAB_API_PRIVATE_TOKEN=[token]' and try again!")
        sys.exit(0)
    return token

def request_json(url, token):
    header = {'PRIVATE-TOKEN': token}
    try:
        response = requests.get(url, headers=header)
        return json.loads(response.text)
    except requests.ConnectionError as e:
        print("Could not connect to given url '{}'. Check connection".format(url))
        sys.exit(0)

def requestGlStatus(result):
    gitlab_token = read_gl_token()
    GITLAB_REMOTE = os.environ.get('GITLAB_REMOTE', None)
    if GITLAB_REMOTE is None:
        remote=cmd("git remote")
        if remote is None or len(remote) == 0:
            print("'git remote' found no suitable branch.")
            sys.exit(0)

    project_url=cmd("git remote get-url {}".format(remote))
    match = re.match(".*@([a-zA-Z0-9\.]*):(.*)\.git", project_url)
    project = match.group(2)
    gl_host = match.group(1)

    if project is None:
        print("could not fetch project!")
        sys.exit(0)
    project_encoded = project.replace("/", "%2F")

    branch = cmd("git rev-parse --abbrev-ref HEAD")
    sha = cmd("git rev-parse {}/{}".format(remote, branch))

    request_url = "http://{}/api/v4/projects/{}/repository/commits/{}".format(gl_host, project_encoded, sha)
    json_result = request_json(request_url, gitlab_token)

    try:
        pl_id = json_result['last_pipeline']['id']
        pl_status = json_result['last_pipeline']['status']
        pl_message = json_result['message']
        pl_url = json_result['last_pipeline']['web_url']
        pl_data = [["branch:", branch], ["status:", color_coded(pl_status)], ["message:", pl_message], ["url:", pl_url]]
        result.add_pipeline_data(pl_data)

        request_url = "http://{}/api/v4/projects/sn%2FSensorNetwork/pipelines/{}/jobs".format(gl_host, pl_id)
        json_result = request_json(request_url, gitlab_token)

        for job in json_result:
            result.add_job_data([job['name'], color_coded(job['status']), job['stage'], job['duration'], job['web_url']])
    except TypeError as e:
        print("Could not parse response json. Usually that happens for a brief time when gitlab creates a new pipeline and its jobs after a push")

def runGlStatus():
    while True:
        try:
            result = Result()
            requestGlStatus(result)
            os.system('clear')
            result.print_tables()
            time.sleep(10)
        except Exception as e:
            print(e)

runGlStatus()
