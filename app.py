import cv2
import numpy as np
import sqlite3
import datetime
import threading
import time
import math
from collections import deque
from flask import Flask, render_template, Response, jsonify
from ultralytics import YOLO

app = Flask(__name__)

MODEL_PATH = r"D:\test\Find-PaperBalls-1\runs\detect\train3\weights\best.pt"

BUFFER_SIZE = 32
PREDICTION_FRAMES = 15
COLLISION_ZONE = 80
GROWTH_THRESHOLD = 0.50
MOVEMENT_THRESHOLD = 2

CONFIDENCE_MIN = 0.50
RATIO_MIN = 0.70
RATIO_MAX = 1.40

EXPOSURE_VAL = 0

# Space Environment Constants
EARTH_RADIUS_KM = 6371.0
ORBITAL_ALTITUDE_KM = 408.0  # ISS altitude
GRAVITATIONAL_CONSTANT = 398600.4418  # Earth's GM in km^3/s^2

# Distance Estimation Constants
MIN_DISTANCE = 10  # Minimum estimated distance in meters
MAX_BASE_DISTANCE = 500  # Maximum base distance for estimation in meters


def init_db():
    conn = sqlite3.connect("orion_logs.db")
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp TEXT, 
                  level TEXT, 
                  message TEXT)"""
    )
    conn.commit()
    conn.close()


init_db()


def log_event(level, message):
    try:
        conn = sqlite3.connect("orion_logs.db")
        c = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO logs (timestamp, level, message) VALUES (?, ?, ?)",
            (timestamp, level, message),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log Error: {e}")


print(f"🔄 SYSTEM BOOT: Loading AI from {MODEL_PATH}...")
try:
    model = YOLO(MODEL_PATH)
    print("✅ AI BRAIN ONLINE.")
except Exception as e:
    print(f"❌ CRITICAL ERROR: Could not load model.\n{e}")
    model = None

system_state = {
    "objects_detected": 0,
    "critical_threats": 0,
    "high_risk": 0,
    "system_status": "OK",
    "maneuver": "NONE",
    "delta_v": "0.000",
    "detected_objects": [],
    "last_log": "",
    "environment": {
        "orbital_velocity": "7.66 km/s",
        "altitude": f"{ORBITAL_ALTITUDE_KM} km",
        "orbital_period": "92.68 min",
        "temperature": "-100°C to +100°C",
        "radiation_level": "Low"
    }
}


class SpaceEnvironment:
    """Simulates orbital mechanics and space environment parameters"""
    
    def __init__(self, altitude_km=ORBITAL_ALTITUDE_KM):
        self.altitude_km = altitude_km
        self.orbital_radius = EARTH_RADIUS_KM + altitude_km
        self.update_orbital_parameters()
        
    def update_orbital_parameters(self):
        """Calculate orbital velocity and period based on altitude"""
        try:
            # Orbital velocity: v = sqrt(GM/r)
            self.orbital_velocity = math.sqrt(GRAVITATIONAL_CONSTANT / self.orbital_radius)
            
            # Orbital period: T = 2π * sqrt(r^3/GM)
            self.orbital_period_seconds = 2 * math.pi * math.sqrt(
                (self.orbital_radius ** 3) / GRAVITATIONAL_CONSTANT
            )
            self.orbital_period_minutes = self.orbital_period_seconds / 60
        except Exception as e:
            print(f"Error calculating orbital parameters: {e}")
            self.orbital_velocity = 7.66
            self.orbital_period_minutes = 92.68
    
    def get_environment_data(self):
        """Returns current space environment parameters"""
        try:
            return {
                "orbital_velocity": f"{self.orbital_velocity:.2f} km/s",
                "altitude": f"{self.altitude_km:.1f} km",
                "orbital_period": f"{self.orbital_period_minutes:.2f} min",
                "temperature": "-100°C to +100°C",
                "radiation_level": "Low"
            }
        except Exception as e:
            print(f"Error getting environment data: {e}")
            return system_state["environment"]


class ObjectClassifier:
    """Classifies detected objects based on their characteristics"""
    
    DEBRIS_TYPES = {
        "small_debris": {"size_range": (0, 30), "risk_multiplier": 1.0, "label": "Small Debris"},
        "medium_debris": {"size_range": (30, 60), "risk_multiplier": 1.5, "label": "Medium Debris"},
        "large_debris": {"size_range": (60, 100), "risk_multiplier": 2.0, "label": "Large Debris"},
        "critical_mass": {"size_range": (100, 1000), "risk_multiplier": 3.0, "label": "Critical Mass"}
    }
    
    @staticmethod
    def classify_object(radius, velocity_magnitude, is_approaching):
        """Classifies object based on size, velocity, and approach vector"""
        try:
            # Determine size class
            debris_type = "small_debris"
            for dtype, params in ObjectClassifier.DEBRIS_TYPES.items():
                min_size, max_size = params["size_range"]
                if min_size <= radius <= max_size:
                    debris_type = dtype
                    break
            
            # Handle objects larger than defined ranges
            if radius > 1000:
                debris_type = "critical_mass"
            
            # Get classification details
            classification = ObjectClassifier.DEBRIS_TYPES[debris_type]
            
            # Calculate enhanced risk level
            base_risk = classification["risk_multiplier"]
            velocity_factor = min(velocity_magnitude / 10.0, 2.0)
            approach_factor = 1.5 if is_approaching else 1.0
            
            risk_score = base_risk * velocity_factor * approach_factor
            
            # Determine risk level
            if risk_score >= 3.0:
                risk_level = "CRITICAL"
            elif risk_score >= 2.0:
                risk_level = "HIGH"
            elif risk_score >= 1.0:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"
            
            return {
                "type": classification["label"],
                "risk_level": risk_level,
                "risk_score": risk_score
            }
        except Exception as e:
            print(f"Error classifying object: {e}")
            return {
                "type": "Unknown Debris",
                "risk_level": "MEDIUM",
                "risk_score": 1.0
            }


# Initialize space environment simulation
space_env = SpaceEnvironment()


class VideoCamera(object):
    def __init__(self):
        self.video = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.video.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.video.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE_VAL)

        self.pos_pts = deque(maxlen=BUFFER_SIZE)
        self.rad_pts = deque(maxlen=BUFFER_SIZE)
        self.last_status = "IDLE"

    def __del__(self):
        self.video.release()

    def calculate_dynamics(self, pos_history, radius_history):
        valid_pos = [p for p in pos_history if p is not None]
        valid_rad = [r for r in radius_history if r is not None]

        if len(valid_pos) < 2 or len(valid_rad) < 5:
            return (0, 0), 0

        limit = min(5, len(valid_pos))
        dx_vals = []
        dy_vals = []

        for i in range(1, limit):
            dx_vals.append(valid_pos[i - 1][0] - valid_pos[i][0])
            dy_vals.append(valid_pos[i - 1][1] - valid_pos[i][1])

        dx = int(np.mean(dx_vals)) if dx_vals else 0
        dy = int(np.mean(dy_vals)) if dy_vals else 0

        r_now = np.mean(valid_rad[:5])
        r_old = np.mean(valid_rad[-5:]) if len(valid_rad) >= 5 else r_now
        growth_rate = r_now - r_old

        return (dx, dy), growth_rate

    def get_direction_label(self, dx, dy):
        h_dir = ""
        v_dir = ""
        if dx > MOVEMENT_THRESHOLD:
            h_dir = "RIGHT"
        elif dx < -MOVEMENT_THRESHOLD:
            h_dir = "LEFT"
        if dy > MOVEMENT_THRESHOLD:
            v_dir = "DOWN"
        elif dy < -MOVEMENT_THRESHOLD:
            v_dir = "UP"
        if h_dir == "" and v_dir == "":
            return "STATIONARY"
        return f"{h_dir} {v_dir}".strip()

    def get_frame(self):
        try:
            success, frame = self.video.read()
            if not success:
                return None

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            center_x, center_y = w // 2, h // 2

            if model:
                results = model(frame, stream=True, verbose=False, conf=0.40)
            else:
                results = []

            current_objects_data = []
            critical_count = 0
            status_msg = "SCANNING SECTOR..."
            status_color = (0, 255, 0)
            vector_text = "NO TARGET"

            target_found = False
            x, y, radius = 0, 0, 0

            if model:
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        confidence = float(box.conf[0])
                        if confidence < CONFIDENCE_MIN:
                            continue

                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        obj_w = x2 - x1
                        obj_h = y2 - y1
                        aspect_ratio = obj_w / float(obj_h)

                        if aspect_ratio < RATIO_MIN or aspect_ratio > RATIO_MAX:
                            continue

                        target_found = True
                        x = x1 + (obj_w // 2)
                        y = y1 + (obj_h // 2)
                        radius = max(obj_w, obj_h) // 2

                        self.pos_pts.appendleft((x, y))
                        self.rad_pts.appendleft(radius)
                        break
                    if target_found:
                        break

            if not target_found:
                self.pos_pts.appendleft(None)
                self.rad_pts.appendleft(None)
                system_state["maneuver"] = "NONE"
                system_state["delta_v"] = "0.000"

            if target_found:
                (dx, dy), growth_rate = self.calculate_dynamics(self.pos_pts, self.rad_pts)
                direction_label = self.get_direction_label(dx, dy)
                z_label = "APPROACHING" if growth_rate > GROWTH_THRESHOLD else "STABLE"

                pred_x = int(x + (dx * PREDICTION_FRAMES))
                pred_y = int(y + (dy * PREDICTION_FRAMES))
                dist_future = np.linalg.norm(
                    np.array((pred_x, pred_y)) - np.array((center_x, center_y))
                )

                is_intercept = dist_future < COLLISION_ZONE
                is_approaching = growth_rate > GROWTH_THRESHOLD

                # Calculate velocity magnitude for classification
                velocity_magnitude = math.sqrt(dx**2 + dy**2)
                
                # Classify the object
                classification = ObjectClassifier.classify_object(radius, velocity_magnitude, is_approaching)
                
                risk_level = classification["risk_level"]
                object_type = classification["type"]

                if is_intercept and is_approaching:
                    status_color = (0, 0, 255)
                    status_msg = "⚠️ COLLISION COURSE"
                    risk_level = "CRITICAL"
                    critical_count = 1

                    dodge_x = "RIGHT" if dx < 0 else "LEFT"
                    dodge_y = "DOWN" if dy < 0 else "UP"

                    system_state["maneuver"] = f"THRUST {dodge_x}-{dodge_y}"
                    system_state["delta_v"] = "1.240 km/s"

                    cv2.putText(
                        frame,
                        f"ACTION: THRUST {dodge_x} & {dodge_y}",
                        (50, h - 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 255),
                        2,
                    )
                    cv2.line(frame, (int(x), int(y)), (center_x, center_y), (0, 0, 255), 3)

                elif is_intercept and not is_approaching:
                    status_color = (255, 100, 0)
                    status_msg = "TRAJECTORY INTERSECT (SAFE)"
                    risk_level = "HIGH"
                    system_state["maneuver"] = "NONE"
                else:
                    status_color = (0, 255, 255)
                    status_msg = "TRACKING TARGET"
                    system_state["maneuver"] = "MAINTAIN"

                vector_text = f"V: {direction_label} | Z: {z_label}"

                cv2.circle(frame, (int(x), int(y)), int(radius), status_color, 2)
                cv2.circle(frame, (int(x), int(y)), 2, status_color, -1)

                if abs(dx) > 1 or abs(dy) > 1:
                    cv2.arrowedLine(
                        frame, (int(x), int(y)), (pred_x, pred_y), (0, 255, 255), 3
                    )

                # Add object type label on video feed
                cv2.putText(
                    frame,
                    object_type,
                    (int(x) - 40, int(y) - int(radius) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    status_color,
                    2,
                )

                # Estimate distance based on size (inverse relationship)
                estimated_distance = max(MIN_DISTANCE, MAX_BASE_DISTANCE - (radius * 2))
                
                current_objects_data.append(
                    {
                        "id": "OBJ_001",
                        "type": object_type,
                        "distance": f"{estimated_distance:.2f}m",
                        "risk": risk_level,
                    }
                )

            for i in range(1, len(self.pos_pts)):
                if self.pos_pts[i - 1] is None or self.pos_pts[i] is None:
                    continue
                thickness = int(np.sqrt(BUFFER_SIZE / float(i + 1)) * 2.5)
                cv2.line(
                    frame, self.pos_pts[i - 1], self.pos_pts[i], (0, 0, 255), thickness
                )

            cv2.rectangle(frame, (0, 0), (w, 100), (0, 0, 0), -1)
            cv2.putText(
                frame,
                "AADES AUTONOMOUS SENSOR",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (150, 150, 150),
                1,
            )
            cv2.putText(
                frame, status_msg, (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2
            )
            cv2.putText(
                frame,
                vector_text,
                (20, 95),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

            cv2.line(
                frame,
                (center_x - 20, center_y),
                (center_x + 20, center_y),
                (100, 100, 100),
                1,
            )
            cv2.line(
                frame,
                (center_x, center_y - 20),
                (center_x, center_y + 20),
                (100, 100, 100),
                1,
            )
            cv2.circle(frame, (center_x, center_y), COLLISION_ZONE, (50, 50, 50), 1)

            system_state["objects_detected"] = 1 if target_found else 0
            system_state["critical_threats"] = critical_count
            system_state["system_status"] = status_msg
            system_state["detected_objects"] = current_objects_data

            if status_msg != self.last_status:
                log_type = "CRITICAL" if critical_count > 0 else "INFO"
                log_event(
                    log_type,
                    f"Status Change: {status_msg} - Maneuver: {system_state['maneuver']}",
                )
                self.last_status = status_msg

            ret, jpeg = cv2.imencode(".jpg", frame)
            return jpeg.tobytes()
        except Exception as e:
            print(f"Error in get_frame: {e}")
            # Return a blank frame on error to prevent crashes
            blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank_frame, "Camera Error", (200, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            ret, jpeg = cv2.imencode(".jpg", blank_frame)
            return jpeg.tobytes()


@app.route("/")
def index():
    return render_template("index.html")


def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame:
            yield (
                b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n\r\n"
            )


@app.route("/video_feed")
def video_feed():
    return Response(
        gen(VideoCamera()), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/telemetry")
def telemetry():
    try:
        conn = sqlite3.connect("orion_logs.db")
        c = conn.cursor()
        c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 5")
        logs = c.fetchall()
        conn.close()

        formatted_logs = []
        for log in logs:
            formatted_logs.append(f"[{log[1].split()[1]}] {log[2]}: {log[3]}")
    except:
        formatted_logs = ["System Log Unavailable"]

    # Update environment data
    try:
        system_state["environment"] = space_env.get_environment_data()
    except Exception as e:
        print(f"Error updating environment: {e}")

    return jsonify({"metrics": system_state, "logs": formatted_logs})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
