import boto3, os, json, calendar
import requests
from base64 import b64decode
from datetime import datetime, timedelta
from os import getenv

os.environ['TZ'] = 'Asia/Tokyo'
api_key = getenv("MACKEREL_API_KEY")

def get_metric_value(namespace, metric_name, dimensions, stats, unit):

    dm = []
    for dimension in dimensions:
        dm.append({'Name': dimension["name"], 'Value': dimension["value"]})
    # print(dm)
    end = datetime.utcnow()
    start = end + timedelta(minutes=-30)
    client = boto3.client('cloudwatch')
    response = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric_name,
        Dimensions=dm,
        StartTime=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        EndTime=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        Period=60,
        Statistics=[
            stats,
        ],
        Unit=unit
    )
    if str(response["ResponseMetadata"]["HTTPStatusCode"]) != "200":
        return False
    if len(response["Datapoints"]) == 0:
        return False
    return sorted(response["Datapoints"], key=lambda x:x['Timestamp'], reverse=True)[0]

def post_service_metric(api_key, url, payload, retry=5, wait=5):

    headers = {'Content-Type': 'application/json', 'X-Api-Key' : api_key}
    print(payload)
    retry_count = 0
    response = None
    while True:
        try:
            res = requests.post(url, data=payload, headers=headers)

        except Exception as e:
            print(e.reason)
        finally:
            if res is not None:
                if res.status_code == 200:
                    return True
            retry_count += 1
            if retry_count >= retry:
                return False
            time.sleep(wait)

def build_params(metric_name, time, value):
  return json.dumps(
    [{
      "name": metric_name,
      "time": time,
      "value": value
    }]
  )

def lambda_handler(event, context):

    print("Received event: " + json.dumps(event, indent=2))

    for input in event:
        mackerel = input['mackerel']
        cloudwatch = input['cloudwatch']
        url = "https://mackerel.io/api/v0/services/" + mackerel["service_name"] + "/tsdb"

        metric = get_metric_value(
            cloudwatch["namespace"],
            cloudwatch["metric_name"],
            cloudwatch["dimensions"],
            cloudwatch["stats"],
            cloudwatch["unit"]
        )
        if metric is False:
            continue
        params = build_params(
            mackerel["metric_name"],
            calendar.timegm(metric["Timestamp"].timetuple()),
            metric[cloudwatch["stats"]]
        )
        result = post_service_metric(api_key=api_key, url=url, payload=params)

        if result is False:
            continue

if __name__ == "__main__":

    f = open("event.json", "r")

    event = json.load(f)
    context = ""
    f.close()

    lambda_handler(event, context)
