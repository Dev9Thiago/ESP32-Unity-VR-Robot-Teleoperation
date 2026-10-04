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


# ============================================================
# CONFIGURATION
# ============================================================

BAUD_RATE = 115200

OUTPUT_FOLDER = "data"

RATE_WINDOW_SECONDS = 3.0


# ============================================================
# APPLICATION
# ============================================================

class BluetoothTestApp:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "ESP32 Haptic Controller - Bluetooth Test"
        )

        self.root.geometry(
            "1050x760"
        )

        # ----------------------------------------------------
        # Serial
        # ----------------------------------------------------

        self.serial_connection = None

        self.connected = False
        self.reading = False

        # ----------------------------------------------------
        # Packet statistics
        # ----------------------------------------------------

        self.packet_count = 0
        self.missing_packets = 0
        self.invalid_packets = 0

        self.last_packet_number = None
        self.latest_esp32_ms = 0

        self.packet_times = deque()

        # ----------------------------------------------------
        # Latency
        # ----------------------------------------------------

        self.pending_pings = {}

        self.rtt_values = []

        self.latest_rtt = None

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        self.csv_file = None
        self.csv_writer = None

        self.start_time = None

        # ----------------------------------------------------
        # GUI
        # ----------------------------------------------------

        self.create_interface()

        self.refresh_ports()

        self.update_statistics_display()

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
            text="Bluetooth Classic SPP Validation",
            font=("Arial", 20, "bold")
        ).pack(
            pady=(15, 5)
        )

        ttk.Label(
            self.root,
            text=(
                "ESP32 Haptic Controller ↔ "
                "Windows PC"
            )
        ).pack(
            pady=(0, 10)
        )

        # ----------------------------------------------------
        # Connection
        # ----------------------------------------------------

        connection = ttk.LabelFrame(
            self.root,
            text="Bluetooth Serial Connection"
        )

        connection.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ttk.Label(
            connection,
            text="COM Port:"
        ).pack(
            side="left",
            padx=(10, 5),
            pady=10
        )

        self.port_variable = tk.StringVar()

        self.port_combo = ttk.Combobox(
            connection,
            textvariable=self.port_variable,
            width=35,
            state="readonly"
        )

        self.port_combo.pack(
            side="left",
            padx=5
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
        # Packet statistics
        # ----------------------------------------------------

        stats = ttk.LabelFrame(
            self.root,
            text="Communication Statistics"
        )

        stats.pack(
            fill="x",
            padx=15,
            pady=5
        )

        self.packet_label = ttk.Label(
            stats,
            text="Packets: 0",
            font=("Arial", 13)
        )

        self.packet_label.grid(
            row=0,
            column=0,
            padx=25,
            pady=12
        )

        self.rate_label = ttk.Label(
            stats,
            text="Rate: 0.00 pkt/s",
            font=("Arial", 13)
        )

        self.rate_label.grid(
            row=0,
            column=1,
            padx=25
        )

        self.missing_label = ttk.Label(
            stats,
            text="Missing: 0",
            font=("Arial", 13)
        )

        self.missing_label.grid(
            row=0,
            column=2,
            padx=25
        )

        self.invalid_label = ttk.Label(
            stats,
            text="Invalid: 0",
            font=("Arial", 13)
        )

        self.invalid_label.grid(
            row=0,
            column=3,
            padx=25
        )

        self.uptime_label = ttk.Label(
            stats,
            text="ESP32 time: 0 ms"
        )

        self.uptime_label.grid(
            row=1,
            column=0,
            columnspan=4,
            pady=(0, 10)
        )

        # ----------------------------------------------------
        # Latency
        # ----------------------------------------------------

        latency = ttk.LabelFrame(
            self.root,
            text="Round-Trip Latency Test"
        )

        latency.pack(
            fill="x",
            padx=15,
            pady=10
        )

        ttk.Button(
            latency,
            text="PING",
            command=self.send_ping
        ).pack(
            side="left",
            padx=15,
            pady=15
        )

        ttk.Button(
            latency,
            text="10x PING TEST",
            command=self.start_multi_ping
        ).pack(
            side="left",
            padx=5
        )

        self.latest_rtt_label = ttk.Label(
            latency,
            text="Latest RTT: -- ms",
            font=("Arial", 12)
        )

        self.latest_rtt_label.pack(
            side="left",
            padx=20
        )

        self.average_rtt_label = ttk.Label(
            latency,
            text="Average RTT: -- ms"
        )

        self.average_rtt_label.pack(
            side="left",
            padx=10
        )

        # ----------------------------------------------------
        # Commands
        # ----------------------------------------------------

        commands = ttk.LabelFrame(
            self.root,
            text="Bidirectional Communication"
        )

        commands.pack(
            fill="x",
            padx=15,
            pady=5
        )

        ttk.Button(
            commands,
            text="HELLO",
            command=lambda:
                self.send_command("HELLO")
        ).pack(
            side="left",
            padx=10,
            pady=15
        )

        ttk.Button(
            commands,
            text="STATUS",
            command=lambda:
                self.send_command("STATUS")
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            commands,
            text="Reset Statistics",
            command=self.reset_statistics
        ).pack(
            side="right",
            padx=15
        )

        # ----------------------------------------------------
        # Log
        # ----------------------------------------------------

        log_frame = ttk.LabelFrame(
            self.root,
            text="Bluetooth Communication Log"
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
            side="left",
            fill="both",
            expand=True,
            padx=(5, 0),
            pady=5
        )

        scrollbar = ttk.Scrollbar(
            log_frame,
            command=self.log.yview
        )

        scrollbar.pack(
            side="right",
            fill="y",
            pady=5,
            padx=(0, 5)
        )

        self.log.config(
            yscrollcommand=scrollbar.set
        )


    # ========================================================
    # PORTS
    # ========================================================

    def refresh_ports(self):

        ports = list(
            serial.tools.list_ports.comports()
        )

        display_values = []

        self.port_map = {}

        for port in ports:

            display = (
                f"{port.device} - "
                f"{port.description}"
            )

            display_values.append(
                display
            )

            self.port_map[
                display
            ] = port.device

        self.port_combo[
            "values"
        ] = display_values

        if display_values:

            self.port_variable.set(
                display_values[0]
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
                "Bluetooth",
                "Select a COM port."
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

            self.connection_label.config(
                text=f"CONNECTED - {port}"
            )

            self.connect_button.config(
                text="Disconnect"
            )

            self.start_csv()

            self.add_log(
                "PC",
                f"Connected to {port}"
            )

            threading.Thread(
                target=self.serial_reader,
                daemon=True
            ).start()

            time.sleep(0.1)

            self.send_command(
                "HELLO"
            )

        except serial.SerialException as error:

            messagebox.showerror(
                "Connection Error",
                str(error)
            )


    def disconnect(self):

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

        self.add_log(
            "PC",
            "Disconnected"
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
                    lambda text=line,
                           rt=receive_time:
                    self.process_message(
                        text,
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
    # PROCESS MESSAGE
    # ========================================================

    def process_message(
        self,
        message,
        receive_time
    ):

        # ----------------------------------------------------
        # DATA packet
        # DATA,counter,millis
        # ----------------------------------------------------

        if message.startswith(
            "DATA,"
        ):

            try:

                parts = message.split(",")

                if len(parts) != 3:
                    raise ValueError

                packet_number = int(
                    parts[1]
                )

                esp32_ms = int(
                    parts[2]
                )

                self.process_data_packet(
                    packet_number,
                    esp32_ms
                )

            except ValueError:

                self.invalid_packets += 1

                self.add_log(
                    "ERROR",
                    message
                )

            return


        # ----------------------------------------------------
        # PONG
        # ----------------------------------------------------

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

                rtt_ms = (
                    receive_time -
                    start
                ) * 1000.0

                self.rtt_values.append(
                    rtt_ms
                )

                self.latest_rtt = rtt_ms

                self.latest_rtt_label.config(
                    text=(
                        f"Latest RTT: "
                        f"{rtt_ms:.2f} ms"
                    )
                )

                average = statistics.mean(
                    self.rtt_values
                )

                self.average_rtt_label.config(
                    text=(
                        f"Average RTT: "
                        f"{average:.2f} ms"
                    )
                )

                self.save_csv(
                    "PONG",
                    identifier,
                    f"{rtt_ms:.4f}"
                )

                self.add_log(
                    "ESP32",
                    (
                        f"PONG {identifier} "
                        f"RTT={rtt_ms:.2f} ms"
                    )
                )

            return


        # ----------------------------------------------------
        # Other message
        # ----------------------------------------------------

        self.add_log(
            "ESP32",
            message
        )

        self.save_csv(
            "MESSAGE",
            message,
            ""
        )


    # ========================================================
    # DATA PACKETS
    # ========================================================

    def process_data_packet(
        self,
        packet_number,
        esp32_ms
    ):

        now = time.time()

        self.packet_count += 1

        self.latest_esp32_ms = (
            esp32_ms
        )

        # ----------------------------------------------------
        # Missing packet detection
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
        # Rate measurement
        # ----------------------------------------------------

        self.packet_times.append(
            now
        )

        cutoff = (
            now -
            RATE_WINDOW_SECONDS
        )

        while (
            self.packet_times
            and
            self.packet_times[0]
            < cutoff
        ):
            self.packet_times.popleft()

        self.save_csv(
            "DATA",
            packet_number,
            esp32_ms
        )


    # ========================================================
    # SEND
    # ========================================================

    def send_command(
        self,
        command
    ):

        if not self.connected:

            messagebox.showwarning(
                "Bluetooth",
                "Connect first."
            )

            return

        try:

            self.serial_connection.write(
                (command + "\n")
                .encode("utf-8")
            )

            self.add_log(
                "PC",
                command
            )

        except serial.SerialException:

            messagebox.showerror(
                "Bluetooth",
                "Could not send command."
            )


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


    def start_multi_ping(self):

        if not self.connected:
            return

        def test():

            for _ in range(10):

                if not self.connected:
                    break

                self.root.after(
                    0,
                    self.send_ping
                )

                time.sleep(0.25)

        threading.Thread(
            target=test,
            daemon=True
        ).start()


    # ========================================================
    # STATISTICS
    # ========================================================

    def update_statistics_display(self):

        now = time.time()

        cutoff = (
            now -
            RATE_WINDOW_SECONDS
        )

        while (
            self.packet_times
            and
            self.packet_times[0]
            < cutoff
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
                f"{rate:.2f} pkt/s"
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

        self.uptime_label.config(
            text=(
                f"ESP32 time: "
                f"{self.latest_esp32_ms} ms"
            )
        )

        self.root.after(
            250,
            self.update_statistics_display
        )


    def reset_statistics(self):

        self.packet_count = 0
        self.missing_packets = 0
        self.invalid_packets = 0

        self.last_packet_number = None

        self.packet_times.clear()

        self.rtt_values.clear()

        self.latest_rtt = None

        self.latest_rtt_label.config(
            text="Latest RTT: -- ms"
        )

        self.average_rtt_label.config(
            text="Average RTT: -- ms"
        )

        self.add_log(
            "PC",
            "Statistics reset"
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
                "bluetooth_test_"
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
            "value_1",
            "value_2"
        ])

        self.start_time = time.time()

        self.add_log(
            "PC",
            f"Recording {filename}"
        )


    def save_csv(
        self,
        event_type,
        value1,
        value2
    ):

        if not self.csv_writer:
            return

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

        elapsed = (
            time.time() -
            self.start_time
        )

        self.csv_writer.writerow([
            timestamp,
            f"{elapsed:.4f}",
            event_type,
            value1,
            value2
        ])

        self.csv_file.flush()


    def close_csv(self):

        if self.csv_file:

            self.csv_file.close()

        self.csv_file = None
        self.csv_writer = None


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
            (
                f"[{timestamp}] "
                f"{source}: "
                f"{message}\n"
            )
        )

        self.log.see(
            "end"
        )

        self.log.config(
            state="disabled"
        )


    # ========================================================
    # CONNECTION LOST
    # ========================================================

    def connection_lost(self):

        self.connected = False
        self.reading = False

        self.close_csv()

        self.connection_label.config(
            text="CONNECTION LOST"
        )

        self.connect_button.config(
            text="Connect"
        )

        self.add_log(
            "PC",
            "Bluetooth connection lost"
        )


    # ========================================================
    # CLOSE
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

    app = BluetoothTestApp(root)

    root.mainloop()