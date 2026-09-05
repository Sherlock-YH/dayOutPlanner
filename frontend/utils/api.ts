const API_BASE = "https://dayoutplanner.onrender.com";

export async function loginUser(email: string, password: string) {
  // FastAPI's OAuth2PasswordRequestForm strictly expects x-www-form-urlencoded
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed");

  localStorage.setItem("token", data.access_token);
  return data;
}

export async function signupUser(email: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Signup failed");
  return data;
}

export async function generateItinerary(prompt: string, startLocation: string, startTime: string) {
  const token = localStorage.getItem("token");
  if (!token) throw new Error("Not authenticated. Please log in.");

  const res = await fetch(`${API_BASE}/api/plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`, // Required for the protected route
    },
    body: JSON.stringify({
      prompt,
      start_location: startLocation,
      start_time: startTime,
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem("token");
      window.location.reload(); // Force redirect to login if token expired
    }
    throw new Error(data.detail || "Failed to generate itinerary");
  }

  return data;
}