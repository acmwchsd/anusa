"""HTTP and WebSocket routes, one module per area.

Routes declared with plain `def` run in a worker thread, so slow model work never blocks other requests.
"""
