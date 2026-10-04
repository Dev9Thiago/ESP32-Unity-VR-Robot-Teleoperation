import csv
import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import serial
import serial.tools.list_ports


BAUD_RATE = 115200
DEFAULT_PORT = "COM7"
OUTPUT_FOLDER = "data"


class HapticTestApp:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ESP32 Haptic Controller - Haptic Test"
        )

        self.root.geometry("900x700")

        self.serial_connection = None
        self.connected = False
        self.reading = False

        self.csv_file = None
        self.csv_writer = None
        self.start_time = None

        self.motor1_value = tk.IntVar(value=0)
        self.motor2_value = tk.IntVar(value=0)

        self.create_interface()
        self.refresh_ports()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )


    # ========================================================
    # INTERFACE
    # ========================================================

    def create_interface(self):

        ttk.Label(
            self.root,
            text="Haptic Actuator Validation",
            font=("Arial", 20, "bold")
        ).pack(pady=15)

        # ----------------------------------------------------
        # Connection
        # ----------------------------------------------------

        connection = ttk.LabelFrame(
            self.root,
            text="ESP32 Connection"
        )

        connection.pack(
            fill="x",
            padx=15,
            pady=5
        )

        ttk.Label(
            connection,
            text="Serial Port:"
        ).pack(
            side="left",
            padx=10,
            pady=10
        )

        self.port_variable = tk.StringVar(
            value=DEFAULT_PORT
        )

        self.port_combo = ttk.Combobox(
            connection,
            textvariable=self.port_variable,
            width=12,
            state="readonly"
        )

        self.port_combo.pack(
            side="left"
        )

        ttk.Button(
            connection,
            text="Refresh",
            command=self.refresh_ports
        ).pack(
            side="left",
            padx=5
        )

        self.connect_button = ttk.Button(
            connection,
            text="Connect",
            command=self.toggle_connection
        )

        self.connect_button.pack(
            side="left",
            padx=10
        )

        self.connection_label = ttk.Label(
            connection,
            text="DISCONNECTED",
            font=("Arial", 10, "bold")
        )

        self.connection_label.pack(
            side="left",
            padx=10
        )

        # ----------------------------------------------------
        # Motor controls
        # ----------------------------------------------------

        motor_frame = ttk.LabelFrame(
            self.root,
            text="Manual Motor Control"
        )

        motor_frame.pack(
            fill="x",
            padx=15,
            pady=10
        )

        self.create_motor_control(
            motor_frame,
            "MOTOR 1 - GPIO32",
            self.motor1_value,
            0,
            self.send_motor1
        )

        self.create_motor_control(
            motor_frame,
            "MOTOR 2 - GPIO33",
            self.motor2_value,
            1,
            self.send_motor2
        )

        # ----------------------------------------------------
        # Both motors
        # ----------------------------------------------------

        both_frame = ttk.LabelFrame(
            self.root,
            text="Both Motors"
        )

        both_frame.pack(
            fill="x",
            padx=15,
            pady=5
        )

        self.both_value = tk.IntVar(
            value=25
        )

        ttk.Scale(
            both_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.both_value
        ).pack(
            side="left",
            fill="x",
            expand=True,
            padx=15,
            pady=15
        )

        ttk.Button(
            both_frame,
            text="RUN BOTH",
            command=self.send_both
        ).pack(
            side="left",
            padx=5
        )

        # ----------------------------------------------------
        # Patterns
        # ----------------------------------------------------

        pattern_frame = ttk.LabelFrame(
            self.root,
            text="Haptic Event Patterns"
        )

        pattern_frame.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ttk.Button(
            pattern_frame,
            text="H0 - No Feedback",
            command=lambda:
                self.send_command("H0")
        ).pack(
            side="left",
            expand=True,
            padx=10,
            pady=15
        )

        ttk.Button(
            pattern_frame,
            text="H1 - Object",
            command=lambda:
                self.send_command("H1")
        ).pack(
            side="left",
            expand=True,
            padx=10
        )

        ttk.Button(
            pattern_frame,
            text="H2 - Wall",
            command=lambda:
                self.send_command("H2")
        ).pack(
            side="left",
            expand=True,
            padx=10
        )

        # ----------------------------------------------------
        # Emergency stop
        # ----------------------------------------------------

        ttk.Button(
            self.root,
            text="STOP ALL MOTORS",
            command=self.emergency_stop
        ).pack(
            fill="x",
            padx=150,
            pady=10,
            ipady=10
        )

        # ----------------------------------------------------
        # Event log
        # ----------------------------------------------------

        log_frame = ttk.LabelFrame(
            self.root,
            text="Communication Log"
        )

        log_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=10
        )

        self.log = tk.Text(
            log_frame,
            state="disabled",
            font=("Consolas", 10)
        )

        self.log.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )


    def create_motor_control(
        self,
        parent,
        name,
        variable,
        column,
        command
    ):

        frame = ttk.Frame(parent)

        frame.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=20,
            pady=15
        )

        parent.columnconfigure(
            column,
            weight=1
        )

        ttk.Label(
            frame,
            text=name,
            font=("Arial", 12, "bold")
        ).pack()

        value_label = ttk.Label(
            frame,
            text="0 %"
        )

        value_label.pack(
            pady=5
        )

        def update_label(value):

            value_label.config(
                text=f"{int(float(value))} %"
            )

        ttk.Scale(
            frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=variable,
            command=update_label
        ).pack(
            fill="x",
            pady=5
        )

        ttk.Button(
            frame,
            text="APPLY",
            command=command
        ).pack(
            pady=5
        )


    # ========================================================
    # SERIAL
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


    def toggle_connection(self):

        if self.connected:
            self.disconnect()

        else:
            self.connect()


    def connect(self):

        try:

            self.serial_connection = serial.Serial(
                self.port_variable.get(),
                BAUD_RATE,
                timeout=1
            )

            time.sleep(2)

            self.serial_connection.reset_input_buffer()

            self.connected = True
            self.reading = True

            self.connection_label.config(
                text="CONNECTED"
            )

            self.connect_button.config(
                text="Disconnect"
            )

            self.start_csv()

            threading.Thread(
                target=self.serial_reader,
                daemon=True
            ).start()

            self.send_command(
                "STATUS"
            )

        except serial.SerialException as error:

            messagebox.showerror(
                "Serial Error",
                str(error)
            )


    def disconnect(self):

        if self.connected:

            try:
                self.send_command("STOP")
                time.sleep(0.05)

            except Exception:
                pass

        self.reading = False
        self.connected = False

        if self.serial_connection:

            try:
                self.serial_connection.close()
            except Exception:
                pass

        self.close_csv()

        self.connection_label.config(
            text="DISCONNECTED"
        )

        self.connect_button.config(
            text="Connect"
        )


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

                if line:

                    self.root.after(
                        0,
                        lambda text=line:
                            self.add_log(
                                "ESP32",
                                text
                            )
                    )

            except serial.SerialException:

                break


    # ========================================================
    # COMMANDS
    # ========================================================

    def send_command(
        self,
        command
    ):

        if not self.connected:

            messagebox.showwarning(
                "ESP32",
                "Connect the ESP32 first."
            )

            return

        try:

            message = (
                command + "\n"
            ).encode("utf-8")

            self.serial_connection.write(
                message
            )

            self.add_log(
                "PC",
                command
            )

            self.save_csv(
                command
            )

        except serial.SerialException:

            messagebox.showerror(
                "Serial Error",
                "Could not send command."
            )


    def send_motor1(self):

        value = int(
            self.motor1_value.get()
        )

        self.send_command(
            f"M1,{value}"
        )


    def send_motor2(self):

        value = int(
            self.motor2_value.get()
        )

        self.send_command(
            f"M2,{value}"
        )


    def send_both(self):

        value = int(
            self.both_value.get()
        )

        self.send_command(
            f"BOTH,{value}"
        )


    def emergency_stop(self):

        self.motor1_value.set(0)
        self.motor2_value.set(0)
        self.both_value.set(0)

        self.send_command(
            "STOP"
        )


    # ========================================================
    # LOG
    # ========================================================

    def add_log(
        self,
        source,
        message
    ):

        timestamp = datetime.now().strftime(
            "%H:%M:%S.%f"
        )[:-3]

        self.log.config(
            state="normal"
        )

        self.log.insert(
            "end",
            f"[{timestamp}] {source}: {message}\n"
        )

        self.log.see("end")

        self.log.config(
            state="disabled"
        )


    # ========================================================
    # CSV
    # ========================================================

    def start_csv(self):

        os.makedirs(
            OUTPUT_FOLDER,
            exist_ok=True
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = os.path.join(
            OUTPUT_FOLDER,
            f"haptic_test_{timestamp}.csv"
        )

        self.csv_file = open(
            filename,
            "w",
            newline="",
            encoding="utf-8"
        )

        self.csv_writer = csv.writer(
            self.csv_file
        )

        self.csv_writer.writerow([
            "timestamp",
            "elapsed_s",
            "command"
        ])

        self.start_time = time.time()


    def save_csv(
        self,
        command
    ):

        if not self.csv_writer:
            return

        elapsed = (
            time.time() -
            self.start_time
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

        self.csv_writer.writerow([
            timestamp,
            f"{elapsed:.4f}",
            command
        ])

        self.csv_file.flush()


    def close_csv(self):

        if self.csv_file:

            self.csv_file.close()

        self.csv_file = None
        self.csv_writer = None


    # ========================================================
    # CLOSE
    # ========================================================

    def close_application(self):

        if self.connected:

            try:

                self.serial_connection.write(
                    b"STOP\n"
                )

                time.sleep(0.05)

            except Exception:
                pass

        self.reading = False

        self.close_csv()

        if self.serial_connection:

            try:
                self.serial_connection.close()
            except Exception:
                pass

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = HapticTestApp(root)

    root.mainloop()