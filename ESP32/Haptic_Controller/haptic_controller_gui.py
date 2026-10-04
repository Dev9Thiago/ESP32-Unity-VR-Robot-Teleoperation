import csv
import os
import time
import threading
import statistics
import tkinter as tk

from collections import deque
from datetime import datetime
from tkinter import ttk, messagebox

import serial
import serial.tools.list_ports

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# ============================================================
# CONFIGURATION
# ============================================================

BAUD_RATE = 115200

OUTPUT_FOLDER = "data"

GRAPH_SECONDS = 10.0
RATE_WINDOW_SECONDS = 3.0

EXPECTED_RATE = 50.0


# ============================================================
# APPLICATION
# ============================================================

class HapticControllerGUI:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ESP32 Haptic Controller - Complete Diagnostics"
        )

        self.root.geometry(
            "1250x850"
        )

        self.root.minsize(
            1100,
            760
        )

        # ----------------------------------------------------
        # Serial
        # ----------------------------------------------------

        self.serial_connection = None

        self.connected = False
        self.reading = False

        # ----------------------------------------------------
        # Current controller state
        # ----------------------------------------------------

        self.pitch = 0.0
        self.roll = 0.0

        self.linear = 0.0
        self.angular = 0.0

        self.grab = 0
        self.forward = 0
        self.backward = 0

        # ----------------------------------------------------
        # Packet statistics
        # ----------------------------------------------------

        self.packet_count = 0
        self.missing_packets = 0
        self.invalid_packets = 0

        self.last_packet_number = None

        self.packet_times = deque()

        # ----------------------------------------------------
        # Graph
        # ----------------------------------------------------

        self.graph_time = deque()
        self.graph_pitch = deque()
        self.graph_roll = deque()

        self.connection_start = None

        # ----------------------------------------------------
        # Ping
        # ----------------------------------------------------

        self.pending_pings = {}
        self.rtt_values = []

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        self.csv_file = None
        self.csv_writer = None
        self.csv_start_time = None

        # ----------------------------------------------------
        # GUI
        # ----------------------------------------------------

        self.create_interface()

        self.refresh_ports()

        self.update_statistics()

        self.update_graph()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )


    # ========================================================
    # GUI
    # ========================================================

    def create_interface(self):

        title = ttk.Label(
            self.root,
            text="Haptic Controller - Complete Diagnostics",
            font=("Arial", 20, "bold")
        )

        title.pack(
            pady=(10, 3)
        )


        # ====================================================
        # CONNECTION
        # ====================================================

        connection_frame = ttk.LabelFrame(
            self.root,
            text="Bluetooth Connection"
        )

        connection_frame.pack(
            fill="x",
            padx=12,
            pady=5
        )


        ttk.Label(
            connection_frame,
            text="COM Port:"
        ).pack(
            side="left",
            padx=(10, 5),
            pady=8
        )


        self.port_variable = tk.StringVar()

        self.port_combo = ttk.Combobox(
            connection_frame,
            textvariable=self.port_variable,
            width=38,
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
            padx=5
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


        # ====================================================
        # MAIN INFORMATION
        # ====================================================

        main_frame = ttk.Frame(
            self.root
        )

        main_frame.pack(
            fill="x",
            padx=12,
            pady=5
        )


        # ----------------------------------------------------
        # Orientation
        # ----------------------------------------------------

        orientation_frame = ttk.LabelFrame(
            main_frame,
            text="IMU Orientation"
        )

        orientation_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 5)
        )


        self.pitch_label = ttk.Label(
            orientation_frame,
            text="Pitch\n0.00°",
            font=("Arial", 20, "bold"),
            justify="center"
        )

        self.pitch_label.pack(
            side="left",
            expand=True,
            padx=20,
            pady=15
        )


        self.roll_label = ttk.Label(
            orientation_frame,
            text="Roll\n0.00°",
            font=("Arial", 20, "bold"),
            justify="center"
        )

        self.roll_label.pack(
            side="left",
            expand=True,
            padx=20
        )


        # ----------------------------------------------------
        # Control commands
        # ----------------------------------------------------

        command_frame = ttk.LabelFrame(
            main_frame,
            text="Normalized Robot Commands"
        )

        command_frame.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(5, 0)
        )


        ttk.Label(
            command_frame,
            text="Linear"
        ).grid(
            row=0,
            column=0,
            padx=10,
            pady=8
        )


        self.linear_bar = ttk.Progressbar(
            command_frame,
            orient="horizontal",
            length=230,
            maximum=200
        )

        self.linear_bar.grid(
            row=0,
            column=1,
            padx=5
        )


        self.linear_label = ttk.Label(
            command_frame,
            text="+0.000",
            width=8
        )

        self.linear_label.grid(
            row=0,
            column=2,
            padx=10
        )


        ttk.Label(
            command_frame,
            text="Angular"
        ).grid(
            row=1,
            column=0,
            padx=10,
            pady=8
        )


        self.angular_bar = ttk.Progressbar(
            command_frame,
            orient="horizontal",
            length=230,
            maximum=200
        )

        self.angular_bar.grid(
            row=1,
            column=1,
            padx=5
        )


        self.angular_label = ttk.Label(
            command_frame,
            text="+0.000",
            width=8
        )

        self.angular_label.grid(
            row=1,
            column=2,
            padx=10
        )


        # ====================================================
        # BUTTONS
        # ====================================================

        buttons_frame = ttk.LabelFrame(
            self.root,
            text="Physical Buttons"
        )

        buttons_frame.pack(
            fill="x",
            padx=12,
            pady=5
        )


        indicators = ttk.Frame(
            buttons_frame
        )

        indicators.pack(
            pady=8
        )


        (
            self.grab_canvas,
            self.grab_indicator,
            self.grab_status
        ) = self.create_indicator(
            indicators,
            "GRAB",
            0
        )


        (
            self.forward_canvas,
            self.forward_indicator,
            self.forward_status
        ) = self.create_indicator(
            indicators,
            "FORWARD",
            1
        )


        (
            self.backward_canvas,
            self.backward_indicator,
            self.backward_status
        ) = self.create_indicator(
            indicators,
            "BACKWARD",
            2
        )


        # ====================================================
        # HAPTICS
        # ====================================================

        haptic_frame = ttk.LabelFrame(
            self.root,
            text="Haptic Feedback Commands"
        )

        haptic_frame.pack(
            fill="x",
            padx=12,
            pady=5
        )


        ttk.Button(
            haptic_frame,
            text="H0 - STOP",
            command=lambda:
                self.send_command("H0")
        ).pack(
            side="left",
            expand=True,
            fill="x",
            padx=10,
            pady=10
        )


        ttk.Button(
            haptic_frame,
            text="H1 - OBJECT",
            command=lambda:
                self.send_command("H1")
        ).pack(
            side="left",
            expand=True,
            fill="x",
            padx=10
        )


        ttk.Button(
            haptic_frame,
            text="H2 - WALL",
            command=lambda:
                self.send_command("H2")
        ).pack(
            side="left",
            expand=True,
            fill="x",
            padx=10
        )


        # ====================================================
        # GRAPH
        # ====================================================

        graph_frame = ttk.LabelFrame(
            self.root,
            text="Live Pitch / Roll"
        )

        graph_frame.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=5
        )


        self.figure = Figure(
            figsize=(8, 3),
            dpi=100
        )

        self.axis = self.figure.add_subplot(
            111
        )

        self.axis.set_xlabel(
            "Time [s]"
        )

        self.axis.set_ylabel(
            "Angle [deg]"
        )

        self.axis.set_ylim(
            -45,
            45
        )

        self.axis.grid(
            True,
            alpha=0.3
        )


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

        self.axis.legend(
            loc="upper right"
        )


        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=graph_frame
        )

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True
        )


        # ====================================================
        # STATISTICS
        # ====================================================

        statistics_frame = ttk.LabelFrame(
            self.root,
            text="Communication Statistics"
        )

        statistics_frame.pack(
            fill="x",
            padx=12,
            pady=5
        )


        self.packet_label = ttk.Label(
            statistics_frame,
            text="Packets: 0"
        )

        self.packet_label.pack(
            side="left",
            padx=15,
            pady=8
        )


        self.rate_label = ttk.Label(
            statistics_frame,
            text="Rate: 0.00 Hz"
        )

        self.rate_label.pack(
            side="left",
            padx=15
        )


        self.missing_label = ttk.Label(
            statistics_frame,
            text="Missing: 0"
        )

        self.missing_label.pack(
            side="left",
            padx=15
        )


        self.invalid_label = ttk.Label(
            statistics_frame,
            text="Invalid: 0"
        )

        self.invalid_label.pack(
            side="left",
            padx=15
        )


        self.rtt_label = ttk.Label(
            statistics_frame,
            text="RTT: -- ms"
        )

        self.rtt_label.pack(
            side="left",
            padx=15
        )


        ttk.Button(
            statistics_frame,
            text="PING",
            command=self.send_ping
        ).pack(
            side="right",
            padx=10
        )


        ttk.Button(
            statistics_frame,
            text="STATUS",
            command=lambda:
                self.send_command("STATUS")
        ).pack(
            side="right",
            padx=5
        )


    # ========================================================
    # BUTTON INDICATOR
    # ========================================================

    def create_indicator(
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
            padx=80
        )


        canvas = tk.Canvas(
            frame,
            width=65,
            height=65,
            highlightthickness=0
        )

        canvas.pack()


        indicator = canvas.create_oval(
            8,
            8,
            57,
            57,
            fill="gray",
            outline="black",
            width=2
        )


        ttk.Label(
            frame,
            text=name,
            font=("Arial", 11, "bold")
        ).pack()


        status = ttk.Label(
            frame,
            text="RELEASED"
        )

        status.pack()


        return (
            canvas,
            indicator,
            status
        )


    # ========================================================
    # PORTS
    # ========================================================

    def refresh_ports(self):

        ports = list(
            serial.tools.list_ports.comports()
        )

        self.port_map = {}

        values = []


        for port in ports:

            display = (
                f"{port.device} - "
                f"{port.description}"
            )

            values.append(
                display
            )

            self.port_map[
                display
            ] = port.device


        self.port_combo[
            "values"
        ] = values


        # Prefer COM4 if currently available,
        # but do not hard-code it.
        preferred = None

        for display in values:

            if display.startswith(
                "COM4 "
            ):
                preferred = display
                break


        if preferred:

            self.port_variable.set(
                preferred
            )

        elif values:

            self.port_variable.set(
                values[0]
            )


    # ========================================================
    # CONNECTION
    # ========================================================

    def toggle_connection(self):

        if self.connected:
            self.disconnect()

        else:
            self.connect()


    def connect(self):

        selection = (
            self.port_variable.get()
        )


        if not selection:

            messagebox.showwarning(
                "Connection",
                "Select a Bluetooth COM port."
            )

            return


        port = self.port_map.get(
            selection
        )


        try:

            self.serial_connection = (
                serial.Serial(
                    port,
                    BAUD_RATE,
                    timeout=0.2
                )
            )


            self.connected = True
            self.reading = True

            self.connection_start = (
                time.perf_counter()
            )


            self.connection_label.config(
                text=(
                    f"CONNECTED - {port}"
                )
            )


            self.connect_button.config(
                text="Disconnect"
            )


            self.reset_runtime_data()

            self.start_csv()


            threading.Thread(
                target=self.serial_reader,
                daemon=True
            ).start()


            self.add_log_to_csv(
                "CONNECTION",
                f"Connected {port}"
            )


            time.sleep(0.1)

            self.send_command(
                "HELLO"
            )


        except serial.SerialException as error:

            messagebox.showerror(
                "Serial Error",
                str(error)
            )


    def disconnect(self):

        if self.connected:

            try:

                self.serial_connection.write(
                    b"H0\n"
                )

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


                if not line:
                    continue


                receive_time = (
                    time.perf_counter()
                )


                self.root.after(
                    0,
                    lambda msg=line,
                           rt=receive_time:
                    self.process_message(
                        msg,
                        rt
                    )
                )


            except serial.SerialException:

                self.root.after(
                    0,
                    self.connection_lost
                )

                break


    # ========================================================
    # MESSAGE PROCESSING
    # ========================================================

    def process_message(
        self,
        message,
        receive_time
    ):

        if message.startswith(
            "CTRL,"
        ):

            self.process_control_packet(
                message
            )

            return


        if message.startswith(
            "PONG,"
        ):

            identifier = (
                message.split(
                    ",",
                    1
                )[1]
            )


            if identifier in self.pending_pings:

                start = (
                    self.pending_pings.pop(
                        identifier
                    )
                )


                rtt = (
                    receive_time -
                    start
                ) * 1000.0


                self.rtt_values.append(
                    rtt
                )


                average = statistics.mean(
                    self.rtt_values
                )


                self.rtt_label.config(
                    text=(
                        f"RTT: "
                        f"{rtt:.2f} ms "
                        f"(avg {average:.2f})"
                    )
                )


                self.add_log_to_csv(
                    "RTT",
                    f"{rtt:.4f}"
                )


            return


        self.add_log_to_csv(
            "MESSAGE",
            message
        )


    # ========================================================
    # CONTROL PACKET
    # ========================================================

    def process_control_packet(
        self,
        packet
    ):

        try:

            fields = (
                packet.split(",")
            )


            if len(fields) != 9:

                raise ValueError(
                    "Incorrect field count"
                )


            values = {}


            for field in fields[1:]:

                key, value = (
                    field.split(
                        ":",
                        1
                    )
                )

                values[key] = value


            required = {
                "P",
                "R",
                "L",
                "A",
                "G",
                "F",
                "B",
                "N"
            }


            if set(values.keys()) != required:

                raise ValueError(
                    "Incorrect packet fields"
                )


            pitch = float(
                values["P"]
            )

            roll = float(
                values["R"]
            )

            linear = float(
                values["L"]
            )

            angular = float(
                values["A"]
            )

            grab = int(
                values["G"]
            )

            forward = int(
                values["F"]
            )

            backward = int(
                values["B"]
            )

            packet_number = int(
                values["N"]
            )


            if grab not in (0, 1):
                raise ValueError

            if forward not in (0, 1):
                raise ValueError

            if backward not in (0, 1):
                raise ValueError


        except (
            ValueError,
            KeyError
        ):

            self.invalid_packets += 1

            return


        # ----------------------------------------------------
        # Missing packets
        # ----------------------------------------------------

        if self.last_packet_number is not None:

            expected = (
                self.last_packet_number + 1
            )


            if packet_number > expected:

                self.missing_packets += (
                    packet_number -
                    expected
                )


        self.last_packet_number = (
            packet_number
        )


        # ----------------------------------------------------
        # Store current values
        # ----------------------------------------------------

        self.pitch = pitch
        self.roll = roll

        self.linear = linear
        self.angular = angular

        self.grab = grab
        self.forward = forward
        self.backward = backward


        self.packet_count += 1


        now = time.perf_counter()

        self.packet_times.append(
            now
        )


        # ----------------------------------------------------
        # Graph
        # ----------------------------------------------------

        if self.connection_start is not None:

            elapsed = (
                now -
                self.connection_start
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


            while (
                self.graph_time
                and
                elapsed -
                self.graph_time[0]
                >
                GRAPH_SECONDS
            ):

                self.graph_time.popleft()
                self.graph_pitch.popleft()
                self.graph_roll.popleft()


        # ----------------------------------------------------
        # GUI
        # ----------------------------------------------------

        self.update_live_values()


        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        self.save_control_csv(
            packet_number
        )


    # ========================================================
    # LIVE VALUES
    # ========================================================

    def update_live_values(self):

        self.pitch_label.config(
            text=(
                "Pitch\n"
                f"{self.pitch:+.2f}°"
            )
        )


        self.roll_label.config(
            text=(
                "Roll\n"
                f"{self.roll:+.2f}°"
            )
        )


        self.linear_label.config(
            text=f"{self.linear:+.3f}"
        )


        self.angular_label.config(
            text=f"{self.angular:+.3f}"
        )


        # Progressbars are mapped:
        #
        # -1 -> 0
        #  0 -> 100
        # +1 -> 200

        self.linear_bar[
            "value"
        ] = (
            self.linear + 1.0
        ) * 100.0


        self.angular_bar[
            "value"
        ] = (
            self.angular + 1.0
        ) * 100.0


        self.set_indicator(
            self.grab_canvas,
            self.grab_indicator,
            self.grab_status,
            self.grab
        )


        self.set_indicator(
            self.forward_canvas,
            self.forward_indicator,
            self.forward_status,
            self.forward
        )


        self.set_indicator(
            self.backward_canvas,
            self.backward_indicator,
            self.backward_status,
            self.backward
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
    # COMMAND TRANSMISSION
    # ========================================================

    def send_command(
        self,
        command
    ):

        if not self.connected:

            messagebox.showwarning(
                "Controller",
                "Connect to the controller first."
            )

            return


        try:

            self.serial_connection.write(
                (
                    command +
                    "\n"
                ).encode(
                    "utf-8"
                )
            )


            self.add_log_to_csv(
                "COMMAND",
                command
            )


        except serial.SerialException:

            self.connection_lost()


    # ========================================================
    # PING
    # ========================================================

    def send_ping(self):

        if not self.connected:
            return


        identifier = str(
            time.time_ns()
        )


        self.pending_pings[
            identifier
        ] = time.perf_counter()


        self.send_command(
            f"PING,{identifier}"
        )


    # ========================================================
    # STATISTICS
    # ========================================================

    def update_statistics(self):

        now = time.perf_counter()

        cutoff = (
            now -
            RATE_WINDOW_SECONDS
        )


        while (
            self.packet_times
            and
            self.packet_times[0]
            <
            cutoff
        ):

            self.packet_times.popleft()


        rate = (
            len(self.packet_times)
            /
            RATE_WINDOW_SECONDS
        )


        self.packet_label.config(
            text=(
                f"Packets: "
                f"{self.packet_count}"
            )
        )


        self.rate_label.config(
            text=(
                f"Rate: "
                f"{rate:.2f} Hz "
                f"/ {EXPECTED_RATE:.0f}"
            )
        )


        self.missing_label.config(
            text=(
                f"Missing: "
                f"{self.missing_packets}"
            )
        )


        self.invalid_label.config(
            text=(
                f"Invalid: "
                f"{self.invalid_packets}"
            )
        )


        self.root.after(
            250,
            self.update_statistics
        )


    # ========================================================
    # GRAPH
    # ========================================================

    def update_graph(self):

        if self.graph_time:

            times = list(
                self.graph_time
            )

            pitch = list(
                self.graph_pitch
            )

            roll = list(
                self.graph_roll
            )


            self.pitch_line.set_data(
                times,
                pitch
            )


            self.roll_line.set_data(
                times,
                roll
            )


            xmax = times[-1]

            xmin = max(
                0,
                xmax -
                GRAPH_SECONDS
            )


            if xmax <= 0:

                xmax = (
                    GRAPH_SECONDS
                )


            self.axis.set_xlim(
                xmin,
                max(
                    GRAPH_SECONDS,
                    xmax
                )
            )


            # Expand vertically if needed.

            max_angle = max(
                45,
                abs(min(pitch)),
                abs(max(pitch)),
                abs(min(roll)),
                abs(max(roll))
            )


            self.axis.set_ylim(
                -max_angle * 1.1,
                max_angle * 1.1
            )


            self.canvas.draw_idle()


        self.root.after(
            100,
            self.update_graph
        )


    # ========================================================
    # RESET RUNTIME DATA
    # ========================================================

    def reset_runtime_data(self):

        self.packet_count = 0
        self.missing_packets = 0
        self.invalid_packets = 0

        self.last_packet_number = None

        self.packet_times.clear()

        self.graph_time.clear()
        self.graph_pitch.clear()
        self.graph_roll.clear()

        self.pending_pings.clear()
        self.rtt_values.clear()

        self.rtt_label.config(
            text="RTT: -- ms"
        )


    # ========================================================
    # CSV
    # ========================================================

    def start_csv(self):

        os.makedirs(
            OUTPUT_FOLDER,
            exist_ok=True
        )


        stamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )


        filename = os.path.join(
            OUTPUT_FOLDER,
            (
                "controller_test_"
                f"{stamp}.csv"
            )
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
            "type",
            "packet",
            "pitch_deg",
            "roll_deg",
            "linear",
            "angular",
            "grab",
            "forward",
            "backward",
            "extra"
        ])


        self.csv_start_time = (
            time.time()
        )


    def save_control_csv(
        self,
        packet_number
    ):

        if not self.csv_writer:
            return


        now = time.time()

        elapsed = (
            now -
            self.csv_start_time
        )


        timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
        )


        self.csv_writer.writerow([
            timestamp,
            f"{elapsed:.4f}",
            "CTRL",
            packet_number,
            f"{self.pitch:.2f}",
            f"{self.roll:.2f}",
            f"{self.linear:.3f}",
            f"{self.angular:.3f}",
            self.grab,
            self.forward,
            self.backward,
            ""
        ])


        self.csv_file.flush()


    def add_log_to_csv(
        self,
        event_type,
        extra
    ):

        if not self.csv_writer:
            return


        now = time.time()

        elapsed = (
            now -
            self.csv_start_time
        )


        timestamp = (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
        )


        self.csv_writer.writerow([
            timestamp,
            f"{elapsed:.4f}",
            event_type,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            extra
        ])


        self.csv_file.flush()


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


    # ========================================================
    # CLOSE
    # ========================================================

    def close_application(self):

        if self.connected:

            try:

                self.serial_connection.write(
                    b"H0\n"
                )

                time.sleep(
                    0.05
                )

            except Exception:

                pass


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

    app = HapticControllerGUI(
        root
    )

    root.mainloop()