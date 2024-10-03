import traceback
from typing import List, Optional, final
from pydantic import BaseModel, Field
from flask import Flask, jsonify, make_response
from flask_pydantic import validate
from do_not_modify import HTTP_STATUS_CREATED, HTTP_STATUS_ERROR, ISO8601_TIMESTAMP_REGEX, HTTP_STATUS_OK, run_db_query

# Use the run_db_query function to run your queries.
app = Flask("acm-uiuc-infra-interview-fa24")


class PostBodyModel(BaseModel):
  event_id: str
  event_description: Optional[str] | None = ""
  start_time: str = Field(pattern=ISO8601_TIMESTAMP_REGEX)
  capacity: Optional[int] = 0
  price: float
  sold: int = 0

class OptimalPriceBodyModel(BaseModel):
  prices: List[float]
  
@app.route("/", methods=["GET"])
def home():
  return make_response("The application is running. Good luck!", HTTP_STATUS_OK)

@app.route("/api/v1/events", methods=["POST"])
@validate()
def post(body: PostBodyModel):
  try:
    body = body.model_dump()
    columns = ', '.join(body.keys())
    placeholders = ':'+', :'.join(body.keys())
    query = 'INSERT INTO events (%s) VALUES (%s)' % (columns, placeholders)
    run_db_query(query, body)
  except Exception:
    print(traceback.format_exc())
    return make_response(jsonify({"error": "Could not write data. Please check your request body."}), HTTP_STATUS_ERROR)  
  return make_response(jsonify(body), HTTP_STATUS_CREATED)
  
@app.route("/api/v1/events", methods=["GET"])
def get():
  try:
    result = run_db_query("SELECT * FROM events;").fetchall()
    for i in range(len(result)):
      if result[i]['capacity'] > result[i]['sold']:
        result[i]['tickets_left'] = True
      else:
        result[i]['tickets_left'] = False
    return make_response(jsonify(result), HTTP_STATUS_OK)
  except Exception:
    return make_response(jsonify({"error": "Could not read data. Please try again."}), HTTP_STATUS_ERROR)

@app.route("/api/v1/events/<string:event_id>/optimal-pricing", methods=["POST"])
@validate(body=OptimalPriceBodyModel)
def pricing(body: OptimalPriceBodyModel, event_id: str):
  body = body.model_dump()
  response_body = {"optimal_price": -1, "tickets_sold": 0, "max_profit": 0}
  try:
    result = run_db_query("SELECT capacity, sold FROM events WHERE event_id = ?;", (event_id, )).fetchone()
    # make sure I have tickets to sell
    capacity, sold = result['capacity'], result['sold']
    if (sold >= capacity):
      return make_response(jsonify(response_body), HTTP_STATUS_OK)
    # figure out how many tickets I can sell
    # trim prices s.t. if there's a ticket shortage, we sell to the highest bidders first.
    prices = body['prices']
    prices.sort()
    tickets_available = min(capacity - sold, len(prices))
    prices = prices[-tickets_available:]
    # run the algo
    final_max_profit = 0
    final_num_sold = len(prices)
    for i in range(len(prices)):
      cand_num_sell = len(prices) - i
      cand_profit = cand_num_sell * prices[i]
      if cand_profit > final_max_profit: # handle tie-breaking correctly
        final_max_profit = cand_profit
        final_num_sold = cand_num_sell
    # send the response
    response_body = {"optimal_price": final_max_profit / final_num_sold, "tickets_sold": final_num_sold, "max_profit": final_max_profit}
    return make_response(jsonify(response_body), HTTP_STATUS_OK)
  except Exception:
    print(traceback.format_exc())
    return make_response(jsonify({"error": "Could not compute data. Please check your request body."}), HTTP_STATUS_ERROR)

if __name__ == "__main__":
  app.run(debug=True, port=8000)
