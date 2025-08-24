#!/usr/bin/env python3
"""
Skrypt do uruchamiania GRISERA API z debuggerem
Użyj: python debug_run.py
"""
import os
import uvicorn
import debugpy

def main():
    # Konfiguracja debuggera
    debugpy.listen(("0.0.0.0", 5678))
    print("🐛 Debugger listening on port 5678")
    print("🔗 Attach VS Code debugger to continue...")
    
    # Czekaj na podłączenie debuggera (opcjonalne)
    # debugpy.wait_for_client()
    
    # Konfiguracja środowiska
    os.environ.setdefault("MONGO_API_HOST", "user:password@localhost")
    os.environ.setdefault("MONGO_API_PORT", "27017")
    os.environ.setdefault("TIMEOUT", "300")
    
    print("🚀 Starting GRISERA API in debug mode...")
    print("📡 API will be available at: http://localhost:8000")
    print("📚 Swagger docs at: http://localhost:8000/docs")
    
    # Uruchom serwer
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        debug=True,
        log_level="debug"
    )

if __name__ == "__main__":
    main() 