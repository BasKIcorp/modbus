import json

from flask import Flask

from lab12.lab12 import lab_12
from lab13.lab13 import lab_13
from lab14.lab14 import lab_14
from lab17.lab17 import lab_17


app = Flask(__name__)
app.register_blueprint(lab_12)
app.register_blueprint(lab_13)
app.register_blueprint(lab_14)
app.register_blueprint(lab_17)
with open('./config.json') as f:
    d = json.load(f)

if __name__ == "__main__":
    app.run(debug=False, port=d["port"])
