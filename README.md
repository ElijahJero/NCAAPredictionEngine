# NCAA Tournament Prediction Tool

A GUI-based NCAA Men's College Basketball Tournament prediction tool that uses Monte Carlo simulation to forecast championship probabilities.

## Features

- Fetches live team stats from the ESPN API
- Monte Carlo simulation with configurable runs
- Customizable stat weights (PPG, defense, rebounds, etc.)
- Head-to-head matchup simulation
- Multiple chart types (bar, pie, treemap)
- Export results to CSV or PNG
- Save/load configurations as JSON

## Requirements

```
pip install requests matplotlib
```

> tkinter is included with Python by default.

## Usage

```
python main.py
```

1. Set the number of teams to load and click **Load Teams & Stats**
2. Adjust stat weights as desired
3. Click **Run Simulation**
4. View results across the Dashboard, Chart, Rankings, and Advanced Stats tabs

## Notes

- Stats are pulled from the ESPN public API and may vary in availability
- `avgPointsAllowed` (opponent PPG) may not always be returned by the API
- Percentage stats (FG%, 3PT%, FT%) are displayed as 0–100 values (e.g. 45.4%)

