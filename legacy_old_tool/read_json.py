import json
import os
import pandas as pd


if __name__ == '__main__':

    json_dir = r"C:\Users\XPENG\Downloads\json"
    json_file_list = os.listdir(json_dir)
    for json_file in json_file_list:
        with open(os.path.join(json_dir, json_file), "r", encoding="utf-8") as f:
            json_data = json.loads(f.read())
            tmp_dict = dict()

            for issue in json_data:
                for key in issue:
                    if key in tmp_dict.keys():
                        tmp_dict[key].append(issue[key])
                    else:
                        tmp_dict[key] = [issue[key]]

                    if key == "folder_path":
                        issue_time = "_".join(issue[key].split("_")[-4:])
                        if "打点时间" in tmp_dict.keys():
                            tmp_dict["打点时间"].append(issue_time)
                        else:
                            tmp_dict["打点时间"] = [issue_time]


            csv_file = json_file.replace(".json", ".csv")
            df_issue = pd.DataFrame(tmp_dict)
            df_issue.to_csv(os.path.join(json_dir, csv_file), index=False)
