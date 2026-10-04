import csv
import os
import time
import threading
import statistics
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from collections import deque

import serial
import serial.tools.list_ports

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ============================================================
# CONFIGURATION
# ============================================================

BAUD_RATE = 115200
DEFAULT_PORT = "COM7"

DISPLAY_SAMPLES = 500

OUTPUT_FOLDER = "data"

GRAPH_UPDATE_MS = 50


# ============================================================
# APPLICATION
# ============================================================

class IMUTestApp:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "MPU6050 Teleoperation Controller Test"
        )

        self.root.geometry("1100x720")

        # ----------------------------------------------------
        # Serial
        # ----------------------------------------------------

        self.serial_connection = None
        self.serial_thread = None

        self.connected = False
        self.reading = False

        # ----------------------------------------------------
        # Recording
        # ----------------------------------------------------

        self.recording = False

        self.csv_file = None
        self.csv_writer = None
        self.csv_filename = None

        self.sample_number = 0
        self.start_time = None

        # ----------------------------------------------------
        # Current IMU data
        # ----------------------------------------------------

        self.current_pitch = 0.0
        self.current_roll = 0.0

        self.current_test = "IDLE"

        # ----------------------------------------------------
        # Data storage
        # ----------------------------------------------------

        self.elapsed_times = []
        self.pitch_values = []
        self.roll_values = []
        self.test_labels = []

        # Display buffers
        self.graph_time = deque(
            maxlen=DISPLAY_SAMPLES
        )

        self.graph_pitch = deque(
            maxlen=DISPLAY_SAMPLES
        )

        self.graph_roll = deque(
            maxlen=DISPLAY_SAMPLES
        )

        # ----------------------------------------------------
        # Master test
        # ----------------------------------------------------

        self.master_running = False
        self.master_thread = None

        # ----------------------------------------------------
        # GUI
        # ----------------------------------------------------

        self.create_interface()

        self.update_graph()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )


    # ========================================================
    # GUI CREATION
    # ========================================================

    def create_interface(self):

        # ----------------------------------------------------
        # Top connection frame
        # ----------------------------------------------------

        connection_frame = ttk.LabelFrame(
            self.root,
            text="ESP32 Connection"
        )

        connection_frame.pack(
            fill="x",
            padx=10,
            pady=10
        )

        ttk.Label(
            connection_frame,
            text="Serial Port:"
        ).pack(
            side="left",
            padx=5
        )

        self.port_variable = tk.StringVar(
            value=DEFAULT_PORT
        )

        self.port_combo = ttk.Combobox(
            connection_frame,
            textvariable=self.port_variable,
            width=15,
            state="readonly"
        )

        self.port_combo.pack(
            side="left",
            padx=5
        )

        self.refresh_ports()

        ttk.Button(
            connection_frame,
            text="Refresh Ports",
            command=self.refresh_ports
        ).pack(
            side="left",
            padx=5
        )

        self.connect_button = ttk.Button(
            connection_frame,
            text="Connect",
            command=self.toggle_connection
        )

        self.connect_button.pack(
            side="left",
            padx=10
        )

        self.connection_label = ttk.Label(
            connection_frame,
            text="DISCONNECTED"
        )

        self.connection_label.pack(
            side="left",
            padx=15
        )

        # ----------------------------------------------------
        # Current measurements
        # ----------------------------------------------------

        measurement_frame = ttk.LabelFrame(
            self.root,
            text="Current MPU6050 Measurement"
        )

        measurement_frame.pack(
            fill="x",
            padx=10,
            pady=5
        )

        self.pitch_label = ttk.Label(
            measurement_frame,
            text="Pitch: 0.00°",
            font=("Arial", 18)
        )

        self.pitch_label.pack(
            side="left",
            padx=30,
            pady=10
        )

        self.roll_label = ttk.Label(
            measurement_frame,
            text="Roll: 0.00°",
            font=("Arial", 18)
        )

        self.roll_label.pack(
            side="left",
            padx=30,
            pady=10
        )

        self.test_label = ttk.Label(
            measurement_frame,
            text="Test: IDLE",
            font=("Arial", 14)
        )

        self.test_label.pack(
            side="right",
            padx=30
        )

        # ----------------------------------------------------
        # Manual tests
        # ----------------------------------------------------

        test_frame = ttk.LabelFrame(
            self.root,
            text="Manual Test Commands"
        )

        test_frame.pack(
            fill="x",
            padx=10,
            pady=5
        )

        commands = [
            ("Neutral", "NEUTRAL"),
            ("Pitch Forward", "PITCH_FORWARD"),
            ("Pitch Backward", "PITCH_BACKWARD"),
            ("Roll Right", "ROLL_RIGHT"),
            ("Roll Left", "ROLL_LEFT")
        ]

        for button_text, command in commands:

            ttk.Button(
                test_frame,
                text=button_text,
                command=lambda c=command:
                    self.set_manual_test(c)
            ).pack(
                side="left",
                padx=5,
                pady=10
            )

        ttk.Button(
            test_frame,
            text="Stop Recording",
            command=self.stop_recording
        ).pack(
            side="right",
            padx=10
        )

        # ----------------------------------------------------
        # Master test
        # ----------------------------------------------------

        master_frame = ttk.LabelFrame(
            self.root,
            text="Automatic Complete Test"
        )

        master_frame.pack(
            fill="x",
            padx=10,
            pady=5
        )

        self.master_button = ttk.Button(
            master_frame,
            text="START MASTER TEST",
            command=self.start_master_test
        )

        self.master_button.pack(
            side="left",
            padx=10,
            pady=10
        )

        self.stage_label = ttk.Label(
            master_frame,
            text="Waiting..."
        )

        self.stage_label.pack(
            side="left",
            padx=20
        )

        self.progress = ttk.Progressbar(
            master_frame,
            orient="horizontal",
            length=300,
            mode="determinate"
        )

        self.progress.pack(
            side="right",
            padx=20
        )

        # ----------------------------------------------------
        # Graph
        # ----------------------------------------------------

        graph_frame = ttk.Frame(
            self.root
        )

        graph_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        self.figure = Figure(
            figsize=(8, 4),
            dpi=100
        )

        self.axis = self.figure.add_subplot(111)

        self.pitch_line, = self.axis.plot(
            [],
            [],
            label="Pitch"
        )

        self.roll_line, = self.axis.plot(
            [],
            [],
            label="Roll"
        )

        self.axis.set_xlabel(
            "Time [s]"
        )

        self.axis.set_ylabel(
            "Angle [deg]"
        )

        self.axis.grid(True)

        self.axis.legend()

        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=graph_frame
        )

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True
        )


    # ========================================================
    # SERIAL PORTS
    # ========================================================

    def refresh_ports(self):

        ports = [
            port.device
            for port
            in serial.tools.list_ports.comports()
        ]

        self.port_combo["values"] = ports

        if DEFAULT_PORT in ports:
            self.port_variable.set(DEFAULT_PORT)

        elif ports:
            self.port_variable.set(ports[0])


    # ========================================================
    # CONNECTION
    # ========================================================

    def toggle_connection(self):

        if not self.connected:
            self.connect_serial()

        else:
            self.disconnect_serial()


    def connect_serial(self):

        port = self.port_variable.get()

        if not port:

            messagebox.showerror(
                "Serial Error",
                "No serial port selected."
            )

            return

        try:

            self.serial_connection = serial.Serial(
                port,
                BAUD_RATE,
                timeout=1
            )

            self.connection_label.config(
                text="CONNECTING / CALIBRATING..."
            )

            self.root.update_idletasks()

            # ESP32 normally resets when serial opens.
            time.sleep(2)

            self.serial_connection.reset_input_buffer()

            self.connected = True
            self.reading = True

            self.connection_label.config(
                text=f"CONNECTED — {port}"
            )

            self.connect_button.config(
                text="Disconnect"
            )

            self.serial_thread = threading.Thread(
                target=self.serial_reader,
                daemon=True
            )

            self.serial_thread.start()

        except serial.SerialException as error:

            messagebox.showerror(
                "Serial Error",
                str(error)
            )


    def disconnect_serial(self):

        self.reading = False
        self.connected = False

        self.stop_recording()

        if self.serial_connection:

            try:
                self.serial_connection.close()
            except:
                pass

        self.connection_label.config(
            text="DISCONNECTED"
        )

        self.connect_button.config(
            text="Connect"
        )


    # ========================================================
    # SERIAL READER
    # ========================================================

    def serial_reader(self):

        while self.reading:

            try:

                line = (
                    self.serial_connection
                    .readline()
                    .decode(
                        "utf-8",
                        errors="ignore"
                    )
                    .strip()
                )

                if not (
                    line.startswith("Pitch:")
                    and ",Roll:" in line
                ):
                    continue

                parts = line.split(",")

                if len(parts) < 4:
                    continue

                pitch = float(
                    parts[0].split(":")[1]
                )

                roll = float(
                    parts[1].split(":")[1]
                )

                linear = float(
                    parts[2].split(":")[1]
                )

                angular = float(
                    parts[3].split(":")[1]
                )

                self.current_pitch = pitch
                self.current_roll = roll

                self.root.after(
                    0,
                    self.update_measurement_labels
                )

                if self.recording:
                    self.store_sample(
                        pitch,
                        roll
                    )

            except (
                ValueError,
                IndexError
            ):
                pass

            except serial.SerialException:

                self.root.after(
                    0,
                    self.serial_lost
                )

                break


    def serial_lost(self):

        self.reading = False
        self.connected = False

        self.connection_label.config(
            text="CONNECTION LOST"
        )

        self.connect_button.config(
            text="Connect"
        )


    # ========================================================
    # MEASUREMENT DISPLAY
    # ========================================================

    def update_measurement_labels(self):

        self.pitch_label.config(
            text=f"Pitch: {self.current_pitch:.2f}°"
        )

        self.roll_label.config(
            text=f"Roll: {self.current_roll:.2f}°"
        )


    # ========================================================
    # RECORDING
    # ========================================================

    def start_recording(self):

        if self.recording:
            return

        os.makedirs(
            OUTPUT_FOLDER,
            exist_ok=True
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        self.csv_filename = os.path.join(
            OUTPUT_FOLDER,
            f"imu_test_{timestamp}.csv"
        )

        self.csv_file = open(
            self.csv_filename,
            "w",
            newline="",
            encoding="utf-8"
        )

        self.csv_writer = csv.writer(
            self.csv_file
        )

        self.csv_writer.writerow([
            "sample",
            "timestamp",
            "elapsed_s",
            "pitch_deg",
            "roll_deg",
            "test"
        ])

        self.elapsed_times.clear()
        self.pitch_values.clear()
        self.roll_values.clear()
        self.test_labels.clear()

        self.graph_time.clear()
        self.graph_pitch.clear()
        self.graph_roll.clear()

        self.sample_number = 0
        self.start_time = time.time()

        self.recording = True


    def stop_recording(self):

        if not self.recording:
            return

        self.recording = False

        if self.csv_file:

            self.csv_file.close()
            self.csv_file = None

        self.current_test = "IDLE"

        self.test_label.config(
            text="Test: IDLE"
        )


    def store_sample(
        self,
        pitch,
        roll
    ):

        current_time = time.time()

        elapsed = (
            current_time -
            self.start_time
        )

        timestamp_string = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
        )

        self.elapsed_times.append(
            elapsed
        )

        self.pitch_values.append(
            pitch
        )

        self.roll_values.append(
            roll
        )

        self.test_labels.append(
            self.current_test
        )

        self.graph_time.append(
            elapsed
        )

        self.graph_pitch.append(
            pitch
        )

        self.graph_roll.append(
            roll
        )

        self.csv_writer.writerow([
            self.sample_number,
            timestamp_string,
            f"{elapsed:.4f}",
            f"{pitch:.4f}",
            f"{roll:.4f}",
            self.current_test
        ])

        self.csv_file.flush()

        self.sample_number += 1


    # ========================================================
    # MANUAL TESTS
    # ========================================================

    def set_manual_test(
        self,
        test_name
    ):

        if not self.connected:

            messagebox.showwarning(
                "ESP32",
                "Connect the ESP32 first."
            )

            return

        if self.master_running:

            messagebox.showwarning(
                "Master Test",
                "A master test is currently running."
            )

            return

        if not self.recording:
            self.start_recording()

        self.current_test = test_name

        self.test_label.config(
            text=f"Test: {test_name}"
        )


    # ========================================================
    # MASTER TEST
    # ========================================================

    def start_master_test(self):

        if not self.connected:

            messagebox.showwarning(
                "ESP32",
                "Connect the ESP32 first."
            )

            return

        if self.master_running:
            return

        response = messagebox.askyesno(
            "Master Test",
            "The complete IMU test will begin.\n\n"
            "Place the controller in its neutral "
            "position.\n\n"
            "Are you ready?"
        )

        if not response:
            return

        if self.recording:
            self.stop_recording()

        self.start_recording()

        self.master_running = True

        self.master_button.config(
            state="disabled"
        )

        self.master_thread = threading.Thread(
            target=self.master_test_sequence,
            daemon=True
        )

        self.master_thread.start()


    def master_test_sequence(self):

        sequence = [

            (
                "NEUTRAL",
                10,
                "Keep the IMU in the NEUTRAL position."
            ),

            (
                "PITCH_FORWARD",
                5,
                "Tilt the IMU FORWARD."
            ),

            (
                "HOLD_PITCH_FORWARD",
                10,
                "Keep the IMU in the FORWARD tilted position."
            ),

            (
                "NEUTRAL",
                5,
                "Return the IMU to NEUTRAL."
            ),

            (
                "PITCH_BACKWARD",
                5,
                "Tilt the IMU BACKWARD."
            ),

            (
                "HOLD_PITCH_BACKWARD",
                10,
                "Keep the IMU in the BACKWARD tilted position."
            ),

            (
                "NEUTRAL",
                5,
                "Return the IMU to NEUTRAL."
            ),

            (
                "ROLL_RIGHT",
                5,
                "Tilt the IMU to the RIGHT."
            ),

            (
                "HOLD_ROLL_RIGHT",
                10,
                "Keep the IMU tilted to the RIGHT."
            ),

            (
                "NEUTRAL",
                5,
                "Return the IMU to NEUTRAL."
            ),

            (
                "ROLL_LEFT",
                5,
                "Tilt the IMU to the LEFT."
            ),

            (
                "HOLD_ROLL_LEFT",
                10,
                "Keep the IMU tilted to the LEFT."
            ),

            (
                "NEUTRAL_FINAL",
                10,
                "Return the IMU to NEUTRAL for the final measurement."
            )
        ]

        total_stages = len(sequence)

        for index, (
            test_name,
            duration,
            instruction
        ) in enumerate(sequence):

            if not self.master_running:
                break

            # -----------------------------------------------
            # Ask user before physical movement stages.
            # -----------------------------------------------

            movement_stage = test_name in [
                "PITCH_FORWARD",
                "PITCH_BACKWARD",
                "ROLL_RIGHT",
                "ROLL_LEFT",
                "NEUTRAL",
                "NEUTRAL_FINAL"
            ]

            if movement_stage:

                ready = self.ask_user_ready(
                    test_name,
                    instruction
                )

                if not ready:

                    self.master_running = False
                    break

            # -----------------------------------------------
            # Run stage
            # -----------------------------------------------

            self.current_test = test_name

            self.root.after(
                0,
                lambda name=test_name:
                    self.test_label.config(
                        text=f"Test: {name}"
                    )
            )

            for second in range(duration):

                if not self.master_running:
                    break

                remaining = (
                    duration - second
                )

                progress_value = (
                    (
                        index +
                        second / duration
                    )
                    /
                    total_stages
                ) * 100.0

                self.root.after(
                    0,
                    lambda inst=instruction,
                           rem=remaining,
                           prog=progress_value:
                    self.update_master_status(
                        inst,
                        rem,
                        prog
                    )
                )

                time.sleep(1)

        self.master_running = False

        self.root.after(
            0,
            self.finish_master_test
        )


    # ========================================================
    # USER CONFIRMATION
    # ========================================================

    def ask_user_ready(
        self,
        test_name,
        instruction
    ):

        event = threading.Event()

        result = {
            "ready": False
        }

        def show_dialog():

            result["ready"] = (
                messagebox.askyesno(
                    f"Next Test: {test_name}",
                    f"{instruction}\n\n"
                    "Position your hands/controller "
                    "as required.\n\n"
                    "Press YES when you are ready "
                    "to perform the movement."
                )
            )

            event.set()

        self.root.after(
            0,
            show_dialog
        )

        event.wait()

        return result["ready"]


    # ========================================================
    # MASTER STATUS
    # ========================================================

    def update_master_status(
        self,
        instruction,
        remaining,
        progress
    ):

        self.stage_label.config(
            text=(
                f"{instruction}   "
                f"{remaining} s"
            )
        )

        self.progress["value"] = progress


    # ========================================================
    # MASTER FINISHED
    # ========================================================

    def finish_master_test(self):

        self.stop_recording()

        self.progress["value"] = 100

        self.stage_label.config(
            text="MASTER TEST COMPLETE"
        )

        self.master_button.config(
            state="normal"
        )

        summary = self.generate_summary()

        messagebox.showinfo(
            "Test Complete",
            "Master IMU test completed.\n\n"
            f"Samples: {len(self.pitch_values)}\n\n"
            f"CSV:\n{self.csv_filename}\n\n"
            f"{summary}"
        )


    # ========================================================
    # SUMMARY
    # ========================================================

    def generate_summary(self):

        if not self.pitch_values:
            return "No valid samples recorded."

        pitch_mean = statistics.mean(
            self.pitch_values
        )

        roll_mean = statistics.mean(
            self.roll_values
        )

        pitch_min = min(
            self.pitch_values
        )

        pitch_max = max(
            self.pitch_values
        )

        roll_min = min(
            self.roll_values
        )

        roll_max = max(
            self.roll_values
        )

        return (
            f"Pitch mean: {pitch_mean:.2f}°\n"
            f"Pitch range: "
            f"{pitch_min:.2f}° to {pitch_max:.2f}°\n\n"
            f"Roll mean: {roll_mean:.2f}°\n"
            f"Roll range: "
            f"{roll_min:.2f}° to {roll_max:.2f}°"
        )


    # ========================================================
    # GRAPH
    # ========================================================

    def update_graph(self):

        if self.graph_time:

            self.pitch_line.set_data(
                list(self.graph_time),
                list(self.graph_pitch)
            )

            self.roll_line.set_data(
                list(self.graph_time),
                list(self.graph_roll)
            )

            self.axis.relim()
            self.axis.autoscale_view()

        self.canvas.draw_idle()

        self.root.after(
            GRAPH_UPDATE_MS,
            self.update_graph
        )


    # ========================================================
    # CLOSE
    # ========================================================

    def close_application(self):

        self.master_running = False
        self.reading = False

        self.stop_recording()

        if self.serial_connection:

            try:
                self.serial_connection.close()
            except:
                pass

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = IMUTestApp(root)

    root.mainloop()