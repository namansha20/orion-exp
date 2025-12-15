"# ORION-EYE: Autonomous Space Debris Detection & Avoidance System

A comprehensive space debris detection and avoidance system featuring real-time object tracking, classification, trajectory prediction, and autonomous decision-making.

## Features

### 1. ✅ Object Detection
- Real-time debris detection using YOLOv8 model
- Custom-trained model for accurate object identification
- Confidence-based filtering for reliable detection

### 2. ✅ Object Classification
- Multi-class debris classification system
- Categories: Small Debris, Medium Debris, Large Debris, Critical Mass
- Size-based classification with risk multipliers
- Velocity and approach vector consideration

### 3. ✅ Trajectory Prediction
- Historical position tracking (32-frame buffer)
- Velocity calculation in X, Y, and Z axes
- Future position prediction using linear extrapolation
- Visual trajectory trails showing object path

### 4. ✅ Collision Risk Assessment
- Real-time collision probability calculation
- Collision zone monitoring (80-pixel radius)
- Multi-level risk assessment (LOW, MEDIUM, HIGH, CRITICAL)
- Approach vector analysis for enhanced accuracy

### 5. ✅ Autonomous Decision Engine
- Intelligent maneuver calculation based on threat level
- Automatic evasion direction determination
- Delta-V calculations for thrust requirements
- Edge case handling for time-critical scenarios

### 6. ✅ Maneuver Simulation
- Real-time thrust direction visualization
- Delta-V cost estimation (km/s)
- Fuel consumption approximation
- Burn duration calculations

### 7. ✅ Space Environment Simulation
- Orbital mechanics calculations
- Dynamic orbital velocity computation (v = √(GM/r))
- Orbital period calculation using Kepler's laws
- Environmental parameters:
  - Orbital velocity: ~7.66 km/s (ISS altitude)
  - Altitude: 408 km (customizable)
  - Orbital period: ~92.68 minutes
  - Temperature range: -100°C to +100°C
  - Radiation level monitoring

### 8. ✅ Explainable Decision Log
- SQLite-based logging system
- Event categorization (INFO, CRITICAL)
- Real-time log display in UI
- Status change tracking with timestamps
- Maneuver decision documentation

## Technical Architecture

### Backend (Flask + Python)
- **app.py**: Main application server
- **SpaceEnvironment**: Orbital mechanics simulation
- **ObjectClassifier**: Debris classification engine
- **VideoCamera**: Real-time video processing and analysis

### Frontend (HTML + TailwindCSS)
- Cyberpunk-themed space operations interface
- Real-time telemetry dashboard
- Multi-panel layout:
  - System Status
  - Space Environment
  - Maneuver Planning
  - Live Camera Feed
  - Detected Objects Table
  - Explainable AI Logs

### Detection Pipeline
1. Video capture from camera
2. YOLO model inference
3. Object filtering (confidence, aspect ratio)
4. Position and size tracking
5. Dynamics calculation (velocity, growth rate)
6. Classification and risk assessment
7. Decision making and maneuver planning
8. Visualization and logging

## Installation

```bash
# Install dependencies
pip install flask opencv-python numpy ultralytics

# Run the application
python app.py
```

## Usage

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open browser and navigate to:
   ```
   http://localhost:5000
   ```

3. The system will automatically:
   - Initialize camera feed
   - Load AI model
   - Begin debris detection
   - Track trajectories
   - Assess collision risks
   - Generate maneuver recommendations

## Configuration

Key parameters in `app.py`:
- `BUFFER_SIZE`: Trajectory history length (default: 32 frames)
- `PREDICTION_FRAMES`: Future prediction distance (default: 15 frames)
- `COLLISION_ZONE`: Danger zone radius (default: 80 pixels)
- `GROWTH_THRESHOLD`: Z-axis approach sensitivity (default: 0.50)
- `CONFIDENCE_MIN`: Minimum detection confidence (default: 0.50)
- `ORBITAL_ALTITUDE_KM`: Simulated orbital altitude (default: 408 km)

## Error Handling

The system includes comprehensive error handling:
- Try-catch blocks around all critical operations
- Graceful degradation on camera/model failures
- Default values for failed calculations
- Error logging for debugging
- Fallback UI displays on component failures

## Future Enhancements

- Multi-object tracking with unique IDs
- 3D trajectory visualization
- Machine learning-based maneuver optimization
- Historical data analysis and reporting
- Integration with real satellite telemetry
- Multi-camera support for enhanced coverage

## License

MIT License

## Contributors

- Original implementation: Camera-based debris tracking
- Enhanced by: Copilot Workspace with advanced features

---

**Note**: This is a simulation system for educational and demonstration purposes. For actual space operations, additional validation and real-world testing would be required." 
