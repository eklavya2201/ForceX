import os
from dotenv import load_dotenv
from backend import create_app

# WSGI hosts such as PythonAnywhere import `application`; Vercel imports `app`. Set FORCEX_SCHEDULER=0
# where background threads are not allowed (the default on Vercel); cleanup then runs from incoming requests.
load_dotenv()
application=create_app(start_scheduler=os.getenv("FORCEX_SCHEDULER","0" if os.getenv("VERCEL") else "1")=="1")
app=application
