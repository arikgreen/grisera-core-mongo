#!/usr/bin/env python3
import os
import sys

# Sprawdź czy to nie jest reload worker
if os.environ.get('RUN_MAIN') == 'true':
    # To jest reload worker - uruchom normalnie bez debuggera
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=80)
else:
    # To jest główny proces - uruchom z debuggerem
    import debugpy
    
    try:
        debugpy.listen(("0.0.0.0", 5678))
        print("🐛 Debugger listening on 0.0.0.0:5678")
        print("🔗 Connect VS Code to continue...")
        print("📡 Application will start after debugger connects")
        
        # Czekaj na połączenie debuggera
        debugpy.wait_for_client()
        print("✅ Debugger connected! Starting application...")
        
    except Exception as e:
        print(f"⚠️ Debugger setup failed: {e}")
        print("🚀 Starting without debugger...")
    
    # Uruchom aplikację
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=80,
        reload=False  # Wyłączamy reload żeby uniknąć problemów z debuggerem
    ) 