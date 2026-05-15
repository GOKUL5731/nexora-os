import psutil

class SystemMonitor:
    def get_stats(self):
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
        except Exception as e:
            print(f"System Monitor Error: {e}")
            return {
                "cpu_percent": 0.0,
                "ram_percent": 0.0,
                "disk_percent": 0.0
            }
