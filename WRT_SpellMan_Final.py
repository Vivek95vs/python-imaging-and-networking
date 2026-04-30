import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import csv

# Accurate double exponential cooling function (given)
def cooling_energy(t):
    return 112.28 * np.exp(-0.04589 * t) + 112.72 * np.exp(-0.02 * t)

class ThermalSimulatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Heating + Cooling Simulator (Unified GUI)")
        self.geometry("1280x900")

        self.segments = []
        self.current_segment = 0
        self.sim_time = 0
        self.segment_time = 0
        self.last_energy = 0
        self.time_data = []
        self.energy_data = []
        self.is_paused = False
        self.sim_speed = 20  # default speed

        self.build_ui()
        self.build_plot()

    def build_ui(self):
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, pady=5)

        ttk.Label(top, text="Power (W):").pack(side=tk.LEFT, padx=5)
        self.power_var = tk.IntVar(value=800)
        self.power_combo = ttk.Combobox(top, textvariable=self.power_var,
                                        values=[0, 100, 200, 300, 400, 500, 600, 800, 1000, 1200, 1500, 1800, 2000, 3000, 4000, 5000],
                                        width=10)
        self.power_combo.pack(side=tk.LEFT)

        ttk.Label(top, text="Duration (sec):").pack(side=tk.LEFT, padx=5)
        self.duration_var = tk.DoubleVar(value=120)
        self.duration_combo = ttk.Combobox(top, textvariable=self.duration_var,
                                           values=[120, 900], width=10)
        self.duration_combo.pack(side=tk.LEFT)

        ttk.Label(top, text="Speed:").pack(side=tk.LEFT, padx=5)
        self.speed_var = tk.DoubleVar(value=20)
        ttk.Entry(top, textvariable=self.speed_var, width=6).pack(side=tk.LEFT)

        ttk.Button(top, text="Add Segment", command=self.add_segment).pack(side=tk.LEFT, padx=10)
        ttk.Button(top, text="Update Selected", command=self.update_segment).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Clear All", command=self.clear_segments).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Start Simulation", command=self.start_simulation).pack(side=tk.LEFT, padx=20)
        self.pause_button = ttk.Button(top, text="Pause", command=self.toggle_pause)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Save CSV", command=self.save_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Save Plot", command=self.save_plot).pack(side=tk.LEFT, padx=5)

        self.tree = ttk.Treeview(self, columns=("Power", "Duration"), show="headings", height=5)
        self.tree.heading("Power", text="Power (W)")
        self.tree.heading("Duration", text="Duration (sec)")
        self.tree.pack(fill=tk.X, pady=10)
        self.tree.bind('<<TreeviewSelect>>', self.load_selected_segment)
        self.tree.bind('<Delete>', self.delete_selected_segment)

        self.status_label = ttk.Label(self, text="", foreground="blue", anchor="center", font=("Arial", 10))
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def build_plot(self):
        self.fig, self.ax = plt.subplots(figsize=(10, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.line, = self.ax.plot([], [], color="darkred", label="Stored Energy (kJ)")
        self.ax.set_title("Energy vs Time")
        self.ax.set_xlabel("Time (min)")
        self.ax.set_ylabel("Stored Energy (kJ)")
        self.ax.grid(True)
        self.ax.legend()

        # Coordinate display label
        self.coord_label = ttk.Label(self, text="X: -, Y: -", font=("Arial", 10))
        self.coord_label.pack(side=tk.BOTTOM, pady=2)

        # Connect mouse movement to coordinate tracker
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
                # Annotation for tooltip
        self.annot = self.ax.annotate("", xy=(0,0), xytext=(10,10),
                                      textcoords="offset points", fontsize=9,
                                      bbox=dict(boxstyle="round", fc="w"),
                                      arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)


    def on_mouse_move(self, event):
        if not event.inaxes:
            self.coord_label.config(text="X: -, Y: -, Z: -")
            self.annot.set_visible(False)
            self.canvas.draw_idle()
            return

        x, y = event.xdata, event.ydata
        self.coord_label.config(text=f"Time: {x*60:.2f} Sec, ENERGY: {y:.2f} KJ, Percentage: {y/2.25:.2f} %")

        if self.time_data:
            # Find the nearest point
            time_array = np.array(self.time_data)
            energy_array = np.array(self.energy_data)
            dist = np.hypot(time_array - x, energy_array - y)
            index = dist.argmin()

            closest_x = time_array[index]
            closest_y = energy_array[index]

            # Show annotation near point
            self.annot.xy = (closest_x, closest_y)
            text = f"Time: {closest_x:.2f} min\nEnergy: {closest_y:.2f} kJ"
            self.annot.set_text(text)
            self.annot.get_bbox_patch().set_alpha(0.8)
            self.annot.set_visible(True)
        else:
            self.annot.set_visible(False)

        self.canvas.draw_idle()


    def add_segment(self):
        power = self.power_var.get()
        duration = self.duration_var.get()
        if duration <= 0:
            self.set_status("Error: Duration must be > 0", "red")
            return
        self.segments.append((power, duration))
        self.tree.insert("", "end", values=(power, duration))
        self.set_status(f"Added: {power}W for {duration} sec", "green")

    def load_selected_segment(self, event):
        selected = self.tree.selection()
        if selected:
            item = selected[0]
            power, duration = self.tree.item(item, 'values')
            self.power_var.set(int(power))
            self.duration_var.set(float(duration))
            self.set_status("Loaded segment for editing. Click 'Update Selected' to apply.", "orange")

    def update_segment(self):
        selected = self.tree.selection()
        if not selected:
            self.set_status("Select a segment to update.", "red")
            return
        item = selected[0]
        index = self.tree.index(item)
        power = self.power_var.get()
        duration = self.duration_var.get()
        if duration <= 0:
            self.set_status("Error: Duration must be > 0", "red")
            return
        self.tree.item(item, values=(power, duration))
        self.segments[index] = (power, duration)
        self.set_status(f"Segment updated to {power}W for {duration} sec.", "green")

    def clear_segments(self):
        self.segments.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.set_status("All segments cleared.", "blue")

    def delete_selected_segment(self, event=None):
        selected = self.tree.selection()
        for item in selected:
            index = self.tree.index(item)
            self.tree.delete(item)
            del self.segments[index]
        self.set_status("Segment deleted.", "blue")

    def start_simulation(self):
        if not self.segments:
            self.set_status("Add at least one segment.", "red")
            return
        self.sim_time = 0
        self.segment_time = 0
        self.current_segment = 0
        self.last_energy = 0
        self.time_data.clear()
        self.energy_data.clear()
        self.is_paused = False

        self.sim_speed = self.speed_var.get() if self.speed_var.get() > 0 else 20

        self.ax.clear()
        self.line, = self.ax.plot([], [], color="darkred", label="Stored Energy (kJ)")
        self.ax.set_title("Real-Time Simulation")
        self.ax.set_xlabel("Time (min)")
        self.ax.set_ylabel("Stored Energy (kJ)")
        self.ax.grid(True)
        self.ax.legend()
        self.canvas.draw()

        self.anim = FuncAnimation(self.fig, self.update_plot, interval=100)
        self.canvas.draw()
        self.set_status("Simulation started...", "blue")

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self.pause_button.config(text="Resume" if self.is_paused else "Pause")
        self.set_status("Paused." if self.is_paused else "Resumed.", "blue")

    def update_plot(self, frame):
        if self.is_paused:
            return
        if self.current_segment >= len(self.segments):
            self.anim.event_source.stop()
            self.set_status("Simulation complete.", "blue")
            return

        dt = (100 / 1000.0) * self.sim_speed  # seconds
        self.sim_time += dt / 60.0  # minutes for x-axis
        self.segment_time += dt  # seconds for physics

        power, duration = self.segments[self.current_segment]

        if self.segment_time <= dt + 1e-6:
            self.segment_start_energy = self.last_energy

        if power > 0:
            slope = power / 16.6667
            energy = self.segment_start_energy + slope * (self.segment_time / 60.0)
        else:
            def scaled_cooling(t):
                return cooling_energy(t) * (self.segment_start_energy / cooling_energy(0))
            energy = scaled_cooling(self.segment_time / 60.0)

        self.time_data.append(self.sim_time)
        self.energy_data.append(energy)
        self.line.set_data(self.time_data, self.energy_data)
        self.ax.set_xlim(0, max(10, self.sim_time + 1))
        self.ax.set_ylim(0, max(250, max(self.energy_data) + 20))
        self.canvas.draw()

        if self.segment_time >= duration:
            self.segment_time = 0
            self.current_segment += 1
            self.last_energy = energy

    def save_csv(self):
        try:
            with open("simulation_output.csv", "w", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Time (min)", "Energy (kJ)"])
                for t, e in zip(self.time_data, self.energy_data):
                    writer.writerow([t, e])
            self.set_status("CSV exported: simulation_output.csv", "green")
        except Exception as e:
            self.set_status(f"CSV export error: {e}", "red")

    def save_plot(self):
        try:
            self.fig.savefig("simulation_plot.png")
            self.set_status("Plot saved as simulation_plot.png", "green")
        except Exception as e:
            self.set_status(f"Plot save error: {e}", "red")

    def set_status(self, msg, color="blue"):
        self.status_label.config(text=msg, foreground=color)

if __name__ == "__main__":
    app = ThermalSimulatorApp()
    app.mainloop()
