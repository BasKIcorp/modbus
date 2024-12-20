import json

from flask import Flask

from lab13_1.lab13_1 import lab_13_1
from lab13_2.lab13_2 import lab_13_2

app = Flask(__name__)
app.register_blueprint(lab_13_1)
app.register_blueprint(lab_13_2)
with open('modbusRESTAPI/config.json') as f:
    d = json.load(f)

if __name__ == "__main__":
    app.run(debug=False, port=d["port"])
