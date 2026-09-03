module.exports = {
  apps: [
    {
      name: "clapos",
      script: "main.py",
      interpreter: "python",
      args: "--debug",
      cwd: "./",
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      max_memory_restart: "1G",
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8"
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./logs/pm2-error.log",
      out_file: "./logs/pm2-out.log",
      merge_logs: true
    }
  ]
};
