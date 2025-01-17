from flask import Flask, session, request, jsonify
import requests
import redis
import hashlib
import re
import secrets
import multiprocessing

app = Flask(__name__)

app.secret_key = secrets.token_hex(16)

redis_client = redis.StrictRedis(
    host='',
    port=,
    password='',
    db=0,
    decode_responses=True
)

# Define the URL of the DATA microservice
MICROSERVICE_URL = "Replace with your Data microservice api url"

def get_answer_for_query(query, num_of_req, cache_key):
    '''
    Checks for the answer in the cache server, if not present then generates it by requesting from the DATA
    microservice.
    Parameters:
    query - the query asked by the user
    num_of_req - the no. of times the user has asked a particular query
    cache_key - the cache key of the corresponding query
    Returns:
    result - the answer generated by the microservice
    link - the link to the answer (as the answer has been scraped from the web)
    status code - a status code indicating the health of the response
    '''
    cached_answer = redis_client.get(cache_key)
    if cached_answer:
        res = cached_answer.split("\/n")
        answer = res[0]
        link_to_answer = res[1]
        return answer, link_to_answer, 200
    else:
        headers = {'Content-Type': 'application/json'}
        payload = {"query": query, "num_of_req": num_of_req}
        res = requests.get(MICROSERVICE_URL, json=payload, headers=headers)
        if res.status_code == 200:
            data = res.json()
            redis_client.setex(cache_key, 3600, str(data['result'] + "\/n" + data['link']))
            return data['result'], data['link'], 200
        else:
            return "Error fetching data from microservice","", 500

def generate_cache_key(query):
    return hashlib.sha256(f"{query}".encode()).hexdigest()

@app.route('/', methods=['GET'])
def index():
    if 'num_of_req' not in session:
        session['num_of_req'] = 1
    req_data = request.get_json()
    try:
        query = req_data['query']
    except:
        return jsonify({'success':False, 'result': 'Please enter a query'}), 500
    if 'query' not in session:
        session['query'] = query
    if query.lower()!=session['query']:
        session['num_of_req'] = 1
    cache_query = query.lower()
    cache_query = re.sub('[^A-Za-z0-9]+', '', cache_query)
    num_of_req = session['num_of_req']
    cache_key = generate_cache_key(f"{cache_query}_{num_of_req}")
    pool = multiprocessing.Pool(processes=4)
    result = pool.apply_async(get_answer_for_query, args=(query, num_of_req, cache_key))
    pool.close()
    pool.join()
    processed_results, link_to_result,statuscode = result.get()
    if statuscode==500:
        return jsonify({'success':False, 'result': 'Error with the deployed api'}), 500
    else:
        session['num_of_req'] += 1
        return jsonify({'success':True, 'result': processed_results, 'link': link_to_result}), 200

if __name__ == '__main__':
    app.run(debug=True)