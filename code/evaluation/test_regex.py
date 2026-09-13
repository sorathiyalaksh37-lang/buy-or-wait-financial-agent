import re
import csv
for row in csv.DictReader(open("dataset/sample_requests.csv")):
    text = row["request_text"]
    m = re.search(r"([A-Z]{3})\s+[\d,\.]+", text)
    if m:
        print(row["request_id"], m.group(1))
    else:
        print(row["request_id"], "NOT FOUND", text)
