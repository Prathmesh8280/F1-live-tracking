# F1 Live Tracker

A Formula 1 race tracking application that displays real-time data during a live race, or the results of the most recent completed race when no race is on.

## What It Shows

### Timing Tower
A live leaderboard showing every driver's current race position, their gap to the race leader, the tyre compound they are running and how many laps old it is, their latest sector times (S1, S2, S3), their last lap time, and their personal best lap time of the race. Drivers who did not finish (DNF) are clearly marked and dimmed.

### Track Map
An SVG circuit map drawn from real GPS telemetry data. The track is divided into three colour-coded sectors — red for S1, yellow for S2, and blue for S3. All 20 drivers are shown as live dots on the map in their team colour with their three-letter code. A chequered start/finish line and a direction arrow show where the lap begins and which way cars travel around the circuit.

### Weather
A strip above the track showing the current conditions at the circuit — air temperature, track temperature, humidity, wind speed and direction, and a rain indicator when it is wet.

## Live vs Finished

The app automatically detects whether a Formula 1 race is currently taking place. If a race is live, all data updates in real time. If there is no active race, the app displays the full results and track map from the most recent completed Grand Prix.
