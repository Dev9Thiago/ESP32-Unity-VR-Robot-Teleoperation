import csv
import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import serial
import serial.tools.list_ports


# ============================================================
# CONFIGURATION
# ============================================================

BAUD_RATE = 115200
DEFAULT_PORT = "COM7"

OUTPUT_FOLDER = "data"


# ============================================================
# APPLICATION
# ============================================================

class ButtonsTestApp:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ESP32 Haptic Controller - Buttons Test"
        )

        self.root.geometry("900x620")
        self.root.minsize(800, 560)

        # ----------------------------------------------------
        # Serial
        # ----------------------------------------------------

        self.serial_connection = None
        self.serial_thread = None

        self.connected = False
        self.reading = False

        # ----------------------------------------------------
        # Button states
        # ----------------------------------------------------

        self.grab_state = 0
        self.forward_state = 0
        self.backward_state = 0

        # ----------------------------------------------------
        # Previous states
        # Used for press counters
        # ----------------------------------------------------

        self.previous_grab = 0
        self.previous_forward = 0
        self.previous_backward = 0

        # ----------------------------------------------------
        # Press counters
        # ----------------------------------------------------

        self.grab_count = 0
        self.forward_count = 0
        self.backward_count = 0

        # ----------------------------------------------------
        # Recording
        # ----------------------------------------------------

        self.csv_file = None
        self.csv_writer = None
        self.csv_filename = None

        self.start_time = None
        self.event_number = 0

        # ----------------------------------------------------
        # GUI
        # ----------------------------------------------------

        self.create_interface()

        self.refresh_ports()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )


    # ========================================================
    # CREATE INTERFACE
    # ========================================================

    def create_interface(self):

        # ----------------------------------------------------
        # Title
        # ----------------------------------------------------

        title = ttk.Label(
            self.root,
            text="Haptic Controller - Button Validation",
            font=("Arial", 20, "bold")
        )

        title.pack(
            pady=(15, 5)
        )

        subtitle = ttk.Label(
            self.root,
            text=(
                "GRAB / AVATAR FORWARD / "
                "AVATAR BACKWARD"
            ),
            font=("Arial", 10)
        )

        subtitle.pack(
            pady=(0, 10)
        )

        # ----------------------------------------------------
        # Connection
        # ----------------------------------------------------

        connection_frame = ttk.LabelFrame(
            self.root,
            text="ESP32 Connection"
        )

        connection_frame.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ttk.Label(
            connection_frame,
            text="Serial Port:"
        ).pack(
            side="left",
            padx=(10, 5),
            pady=10
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

        ttk.Button(
            connection_frame,
            text="Refresh",
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
            text="DISCONNECTED",
            font=("Arial", 10, "bold")
        )

        self.connection_label.pack(
            side="left",
            padx=15
        )

        # ----------------------------------------------------
        # Button indicators
        # ----------------------------------------------------

        indicators_frame = ttk.LabelFrame(
            self.root,
            text="Live Button States"
        )

        indicators_frame.pack(
            fill="x",
            padx=15,
            pady=10
        )

        indicators_container = ttk.Frame(
            indicators_frame
        )

        indicators_container.pack(
            pady=20
        )

        # Grab
        self.grab_canvas, self.grab_indicator = \
            self.create_button_indicator(
                indicators_container,
                "GRAB",
                0
            )

        # Forward
        self.forward_canvas, self.forward_indicator = \
            self.create_button_indicator(
                indicators_container,
                "FORWARD",
                1
            )

        # Backward
        self.backward_canvas, self.backward_indicator = \
            self.create_button_indicator(
                indicators_container,
                "BACKWARD",
                2
            )

        # ----------------------------------------------------
        # Counters
        # ----------------------------------------------------

        counter_frame = ttk.LabelFrame(
            self.root,
            text="Detected Presses"
        )

        counter_frame.pack(
            fill="x",
            padx=15,
            pady=10
        )

        self.grab_counter_label = ttk.Label(
            counter_frame,
            text="Grab: 0",
            font=("Arial", 13)
        )

        self.grab_counter_label.pack(
            side="left",
            expand=True,
            pady=12
        )

        self.forward_counter_label = ttk.Label(
            counter_frame,
            text="Forward: 0",
            font=("Arial", 13)
        )

        self.forward_counter_label.pack(
            side="left",
            expand=True
        )

        self.backward_counter_label = ttk.Label(
            counter_frame,
            text="Backward: 0",
            font=("Arial", 13)
        )

        self.backward_counter_label.pack(
            side="left",
            expand=True
        )

        # ----------------------------------------------------
        # Controls
        # ----------------------------------------------------

        controls_frame = ttk.Frame(
            self.root
        )

        controls_frame.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ttk.Button(
            controls_frame,
            text="Reset Counters",
            command=self.reset_counters
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            controls_frame,
            text="Clear Event Log",
            command=self.clear_event_log
        ).pack(
            side="left",
            padx=5
        )

        # ----------------------------------------------------
        # Event log
        # ----------------------------------------------------

        log_frame = ttk.LabelFrame(
            self.root,
            text="Event Log"
        )

        log_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(5, 15)
        )

        self.event_log = tk.Text(
            log_frame,
            height=10,
            state="disabled",
            font=("Consolas", 10)
        )

        self.event_log.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(5, 0),
            pady=5
        )

        scrollbar = ttk.Scrollbar(
            log_frame,
            command=self.event_log.yview
        )

        scrollbar.pack(
            side="right",
            fill="y",
            padx=(0, 5),
            pady=5
        )

        self.event_log.config(
            yscrollcommand=scrollbar.set
        )


    # ========================================================
    # CREATE BUTTON INDICATOR
    # ========================================================

    def create_button_indicator(
        self,
        parent,
        name,
        column
    ):

        frame = ttk.Frame(
            parent
        )

        frame.grid(
            row=0,
            column=column,
            padx=55
        )

        canvas = tk.Canvas(
            frame,
            width=100,
            height=100,
            highlightthickness=0
        )

        canvas.pack()

        indicator = canvas.create_oval(
            15,
            15,
            85,
            85,
            fill="gray",
            outline="black",
            width=2
        )

        ttk.Label(
            frame,
            text=name,
            font=("Arial", 12, "bold")
        ).pack(
            pady=(0, 5)
        )

        status = ttk.Label(
            frame,
            text="RELEASED"
        )

        status.pack()

        if name == "GRAB":
            self.grab_status_label = status

        elif name == "FORWARD":
            self.forward_status_label = status

        elif name == "BACKWARD":
            self.backward_status_label = status

        return canvas, indicator


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

            self.port_variable.set(
                DEFAULT_PORT
            )

        elif ports:

            self.port_variable.set(
                ports[0]
            )


    # ========================================================
    # CONNECTION
    # ========================================================

    def toggle_connection(self):

        if self.connected:
            self.disconnect_serial()

        else:
            self.connect_serial()


    def connect_serial(self):

        port = self.port_variable.get()

        if not port:

            messagebox.showerror(
                "Connection Error",
                "Select a serial port."
            )

            return

        try:

            self.serial_connection = serial.Serial(
                port,
                BAUD_RATE,
                timeout=1
            )

            self.connection_label.config(
                text="CONNECTING..."
            )

            self.root.update_idletasks()

            # ESP32 may reset when serial port opens.
            time.sleep(2)

            self.serial_connection.reset_input_buffer()

            self.connected = True
            self.reading = True

            self.connection_label.config(
                text=f"CONNECTED - {port}"
            )

            self.connect_button.config(
                text="Disconnect"
            )

            self.start_csv()

            self.add_log(
                f"Connected to {port}"
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

        self.close_csv()

        if self.serial_connection:

            try:
                self.serial_connection.close()

            except Exception:
                pass

        self.connect_button.config(
            text="Connect"
        )

        self.connection_label.config(
            text="DISCONNECTED"
        )

        self.add_log(
            "ESP32 disconnected"
        )


    # ========================================================
    # SERIAL READER
    # ========================================================

    def serial_reader(self):

        while self.reading:

            try:

                raw_line = (
                    self.serial_connection
                    .readline()
                )

                if not raw_line:
                    continue

                line = raw_line.decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                # Expected:
                #
                # Grab:0,Forward:0,Backward:0

                if not line.startswith("Grab:"):
                    continue

                parts = line.split(",")

                if len(parts) != 3:
                    continue

                grab = int(
                    parts[0].split(":")[1]
                )

                forward = int(
                    parts[1].split(":")[1]
                )

                backward = int(
                    parts[2].split(":")[1]
                )

                if grab not in (0, 1):
                    continue

                if forward not in (0, 1):
                    continue

                if backward not in (0, 1):
                    continue

                self.root.after(
                    0,
                    lambda g=grab,
                           f=forward,
                           b=backward:
                    self.process_states(
                        g,
                        f,
                        b
                    )
                )

            except (
                ValueError,
                IndexError
            ):
                continue

            except serial.SerialException:

                self.root.after(
                    0,
                    self.connection_lost
                )

                break


    # ========================================================
    # PROCESS STATES
    # ========================================================

    def process_states(
        self,
        grab,
        forward,
        backward
    ):

        # ----------------------------------------------------
        # Detect rising edges
        # ----------------------------------------------------

        if (
            grab == 1
            and self.previous_grab == 0
        ):
            self.grab_count += 1

            self.add_log(
                "GRAB pressed"
            )

        if (
            forward == 1
            and self.previous_forward == 0
        ):
            self.forward_count += 1

            self.add_log(
                "FORWARD pressed"
            )

        if (
            backward == 1
            and self.previous_backward == 0
        ):
            self.backward_count += 1

            self.add_log(
                "BACKWARD pressed"
            )

        # ----------------------------------------------------
        # Log releases
        # ----------------------------------------------------

        if (
            grab == 0
            and self.previous_grab == 1
        ):
            self.add_log(
                "GRAB released"
            )

        if (
            forward == 0
            and self.previous_forward == 1
        ):
            self.add_log(
                "FORWARD released"
            )

        if (
            backward == 0
            and self.previous_backward == 1
        ):
            self.add_log(
                "BACKWARD released"
            )

        # ----------------------------------------------------
        # Save states
        # ----------------------------------------------------

        self.grab_state = grab
        self.forward_state = forward
        self.backward_state = backward

        self.previous_grab = grab
        self.previous_forward = forward
        self.previous_backward = backward

        # ----------------------------------------------------
        # Update GUI
        # ----------------------------------------------------

        self.update_indicators()
        self.update_counters()

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        self.save_event(
            grab,
            forward,
            backward
        )


    # ========================================================
    # INDICATORS
    # ========================================================

    def update_indicators(self):

        self.set_indicator(
            self.grab_canvas,
            self.grab_indicator,
            self.grab_status_label,
            self.grab_state
        )

        self.set_indicator(
            self.forward_canvas,
            self.forward_indicator,
            self.forward_status_label,
            self.forward_state
        )

        self.set_indicator(
            self.backward_canvas,
            self.backward_indicator,
            self.backward_status_label,
            self.backward_state
        )


    def set_indicator(
        self,
        canvas,
        indicator,
        label,
        state
    ):

        if state:

            canvas.itemconfig(
                indicator,
                fill="green"
            )

            label.config(
                text="PRESSED"
            )

        else:

            canvas.itemconfig(
                indicator,
                fill="gray"
            )

            label.config(
                text="RELEASED"
            )


    # ========================================================
    # COUNTERS
    # ========================================================

    def update_counters(self):

        self.grab_counter_label.config(
            text=f"Grab: {self.grab_count}"
        )

        self.forward_counter_label.config(
            text=f"Forward: {self.forward_count}"
        )

        self.backward_counter_label.config(
            text=f"Backward: {self.backward_count}"
        )


    def reset_counters(self):

        self.grab_count = 0
        self.forward_count = 0
        self.backward_count = 0

        self.update_counters()

        self.add_log(
            "Counters reset"
        )


    # ========================================================
    # EVENT LOG
    # ========================================================

    def add_log(
        self,
        message
    ):

        timestamp = datetime.now().strftime(
            "%H:%M:%S.%f"
        )[:-3]

        self.event_log.config(
            state="normal"
        )

        self.event_log.insert(
            "end",
            f"[{timestamp}] {message}\n"
        )

        self.event_log.see(
            "end"
        )

        self.event_log.config(
            state="disabled"
        )


    def clear_event_log(self):

        self.event_log.config(
            state="normal"
        )

        self.event_log.delete(
            "1.0",
            "end"
        )

        self.event_log.config(
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

        self.csv_filename = os.path.join(
            OUTPUT_FOLDER,
            f"buttons_test_{timestamp}.csv"
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
            "event",
            "timestamp",
            "elapsed_s",
            "grab",
            "forward",
            "backward"
        ])

        self.start_time = time.time()
        self.event_number = 0

        self.add_log(
            f"Recording: {self.csv_filename}"
        )


    def save_event(
        self,
        grab,
        forward,
        backward
    ):

        if self.csv_writer is None:
            return

        now = time.time()

        elapsed = (
            now - self.start_time
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

        self.csv_writer.writerow([
            self.event_number,
            timestamp,
            f"{elapsed:.4f}",
            grab,
            forward,
            backward
        ])

        self.csv_file.flush()

        self.event_number += 1


    def close_csv(self):

        if self.csv_file:

            try:
                self.csv_file.close()

            except Exception:
                pass

        self.csv_file = None
        self.csv_writer = None


    # ========================================================
    # CONNECTION LOST
    # ========================================================

    def connection_lost(self):

        self.reading = False
        self.connected = False

        self.close_csv()

        self.connection_label.config(
            text="CONNECTION LOST"
        )

        self.connect_button.config(
            text="Connect"
        )

        self.add_log(
            "Serial connection lost"
        )


    # ========================================================
    # CLOSE APPLICATION
    # ========================================================

    def close_application(self):

        self.reading = False
        self.connected = False

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

    app = ButtonsTestApp(root)

    root.mainloop()