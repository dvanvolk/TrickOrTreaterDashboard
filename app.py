from flask import Flask, render_template, jsonify
import live_control

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('trickortreat_dashboard.html')

@app.route('/live_status', methods=['GET'])
def get_live_status():
    return jsonify({'live': live_control.is_live()})

@app.route('/toggle_live', methods=['POST'])
def toggle_live():
    live_control.toggle_live()
    return jsonify({'live': live_control.is_live()})

if __name__ == '__main__':
    app.run(debug=True)