import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from claw_runner import run_pipeline

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])

@app.message(".*")
def handle_message(message, say):
    result = run_pipeline()
    say(result["output"])

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
