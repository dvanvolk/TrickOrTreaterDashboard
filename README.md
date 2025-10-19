# Trick-or-Treater Dashboard

## Overview
The Trick-or-Treater Dashboard is a web application designed to track and display live data on Halloween visitors. It provides real-time statistics, charts, and a user-friendly interface for monitoring Trick-or-Treat activity.

## Project Structure
```
trickortreater-dashboard
├── app.py                     # Main entry point of the application
├── live_control.py            # Controls live status and counter visibility
├── requirements.txt           # Project dependencies
├── templates
│   └── trickortreat_dashboard.html  # HTML structure for the dashboard
├── static
│   ├── css
│   │   └── dashboard.css      # CSS styles for the dashboard
│   └── js
│       ├── dashboard.js       # JavaScript for dashboard interactivity
│       └── chart-helpers.js   # Helper functions for chart management
├── data
│   ├── trickortreat_data.json # JSON data for Trick-or-Treater counts
│   └── historical_data.json   # Historical data for comparison
└── README.md                  # Project documentation
```

## Setup Instructions
1. **Clone the repository**:
   ```
   git clone <repository-url>
   cd trickortreater-dashboard
   ```

2. **Install dependencies**:
   Use pip to install the required packages listed in `requirements.txt`:
   ```
   pip install -r requirements.txt
   ```

3. **Run the application**:
   Execute the main application file:
   ```
   python app.py
   ```

4. **Access the dashboard**:
   Open your web browser and navigate to `http://localhost:5000` (or the appropriate port specified in your application).

## Usage
- The dashboard displays live statistics of Trick-or-Treaters.
- You can control the live data display using the provided controls in the application.
- The dashboard features various charts to visualize the data over time.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.