#!/usr/bin/env python3
"""
Simple HTTP server for the News Processing Demo Frontend
"""
import http.server
import socketserver
import webbrowser
import os
import sys
from pathlib import Path

def serve_demo(port=3000):
    """Serve the demo frontend on the specified port"""
    
    # Change to the demo directory
    demo_dir = Path(__file__).parent
    os.chdir(demo_dir)
    
    # Create handler
    Handler = http.server.SimpleHTTPRequestHandler
    
    # Add CORS headers for API calls
    class CORSRequestHandler(Handler):
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()
    
    try:
        with socketserver.TCPServer(("", port), CORSRequestHandler) as httpd:
            print(f"🚀 News Processing Demo Frontend")
            print(f"📡 Serving at: http://localhost:{port}")
            print(f"📁 Directory: {demo_dir}")
            print(f"🔗 Backend API: http://localhost:8000")
            print(f"\n📋 Instructions:")
            print(f"1. Make sure backend is running: cd backend && python -m uvicorn api.main:app --reload")
            print(f"2. Open browser: http://localhost:{port}")
            print(f"3. Click 'Start Real-time Processing' to begin")
            print(f"\n⏹️  Press Ctrl+C to stop the server")
            
            # Try to open browser automatically
            try:
                webbrowser.open(f'http://localhost:{port}')
                print(f"🌐 Browser opened automatically")
            except:
                print(f"🌐 Please open http://localhost:{port} in your browser")
            
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Demo server stopped")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is already in use. Try a different port:")
            print(f"   python serve.py --port 3001")
        else:
            print(f"❌ Server error: {e}")

if __name__ == "__main__":
    port = 3000
    
    # Check for port argument
    if len(sys.argv) > 1:
        if sys.argv[1] == "--port" and len(sys.argv) > 2:
            try:
                port = int(sys.argv[2])
            except ValueError:
                print("❌ Invalid port number")
                sys.exit(1)
        elif sys.argv[1] in ["-h", "--help"]:
            print("News Processing Demo Server")
            print("Usage: python serve.py [--port PORT]")
            print("Default port: 3000")
            sys.exit(0)
    
    serve_demo(port)