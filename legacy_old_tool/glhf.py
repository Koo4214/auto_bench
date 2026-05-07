import traceback

import pandas as pd
import subprocess
import json
import os

class Issue:
    def __init__(self, name, start_time, end_time, mode, folder_path, start_time_str, end_time_str, run_start_time, score,
                 info=""):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.mode = mode
        self.folder_path = folder_path
        self.info = info
        self.start_time_str = start_time_str
        self.end_time_str = end_time_str
        self.run_start_time = run_start_time
        self.score = score

    def to_dict(self):
        return {
            "name": self.name,
            "start_time_str": self.start_time,
            "end_time_str": self.end_time,
            "mode": self.mode,
            "info": self.info,
            "folder_path": self.folder_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "run_start_time": self.run_start_time,
            "score": self.score,
        }

class IssueManager:
    def __init__(self, save_dir):
        self.save_dir = save_dir
        self.issues_file = os.path.join(save_dir, "issue_records", "issues.json")
        self.issues = []
        self.load_issues()

    def load_issues(self):
        issue_records_folder = os.path.join(self.save_dir, "issue_records")
        if not os.path.exists(issue_records_folder):
            os.makedirs(issue_records_folder)
            return

        if os.path.exists(self.issues_file):
            with open(self.issues_file, 'r', encoding='utf-8') as f:
                self.issues = [Issue(**issue) for issue in json.load(f)]

    def save_issues(self):
        with open(self.issues_file, 'w', encoding='utf-8d') as f:
            json.dump([issue.to_dict() for issue in self.issues], f, ensure_ascii=False, indent=4)

    def add_issue(self, issue):
        self.issues.append(issue)
        self.save_issues()

    def get_issues(self):
        return self.issues

def clip_video(input_path, output_path, start_time, end_time):
    print(input_path)
    print(output_path)
    try:
        command = [
            'ffmpeg',
            '-y',
            '-ss', str(start_time),
            '-to', str(end_time),
            '-i', input_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-threads', '0',
            output_path
        ]
        print(" ".join(command))
        process = subprocess.Popen(command, stdin=subprocess.PIPE,stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8', shell=True)
        stdout, stderr = process.communicate()

    except:
        print("ffmpeg error")
        print(traceback.format_exc())

def clip_imu_data(imu_data, issue_start_time, issue_end_time, output_path):
    time_list = list(imu_data.get("时间"))
    start_idx = 0
    end_idx = -1
    for i in range(len(time_list) - 1):
        if time_list[i] <= issue_start_time <= time_list[i + 1]:
            start_idx = i
        if time_list[i] <= issue_end_time <= time_list[i + 1]:
            end_idx = i

    result = dict()

    for key in imu_data.keys():
        result[key] = list(imu_data[key])[start_idx:end_idx]

    with open(os.path.join(output_path, 'imu_data.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    df = pd.DataFrame(result)
    df.to_csv(os.path.join(output_path, 'imu_data.csv'), encoding="utf-8")

if __name__ == '__main__':

    recording_files = [
        "screen_record.avi",
        "camera_1.avi",
        "camera_2.avi",
        "camera_3.avi",
    ]

    save_dir = r"C:\Users\XPENG\Downloads\package\package\dist\test\7-11-F30B"
    issue_manager = IssueManager(save_dir)

    # with open(os.path.join(save_dir, "imu_data.json"), "r", encoding="utf-8") as f:
    #     imu_data = json.loads(f.read())

    for issue in issue_manager.get_issues():
        issue_folder_path = issue.folder_path.replace("Xpeng", "XPENG")
        for video in recording_files:
            target_file = os.path.join(save_dir, video)
            des_file = os.path.join(issue_folder_path, video.replace(".avi", ".mp4"))
            clip_video(target_file, des_file, issue.start_time - issue.run_start_time, issue.end_time - issue.run_start_time)
        # clip_imu_data(imu_data, issue.start_time, issue.end_time, issue_folder_path)
