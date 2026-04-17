let socket = null;

export function connectSocket() {
  if (socket) return socket; // prevent multiple connections

  const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
  const wsHost = window.location.hostname;
  socket = new WebSocket(`${wsProtocol}://${wsHost}:8000/ws`);

  socket.onopen = () => {
    console.log("✅ Connected to backend");
  };

  socket.onmessage = (event) => {
    console.log("📨 Gesture:", JSON.parse(event.data));
  };

  socket.onerror = (error) => {
    console.error("❌ WebSocket error:", error);
  };

  socket.onclose = () => {
    console.log("🔌 Disconnected");
    socket = null;
  };

  return socket;
}
