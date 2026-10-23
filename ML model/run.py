"""
LifeLink: Multi-Parameter Crash Detection with Adaptive False Alarm Suppression
Application Entry Point
"""

import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 72)
    print("  LIFELINK: MULTI-PARAMETER CRASH DETECTION & EMERGENCY SYSTEM")
    print("  Reference: Diana George et al., Dayananda Sagar University")
    print("=" * 72)
    print("  -> Gateway & Overview:      http://localhost:8000/")
    print("  -> Driver In-Car Portal:    http://localhost:8000/user")
    print("  -> Admin & Mock Drill:      http://localhost:8000/admin")
    print("  -> API Swagger Docs:        http://localhost:8000/docs")
    print("=" * 72)
    print("Starting FastAPI server on http://127.0.0.1:8000 ...")
    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=True)
