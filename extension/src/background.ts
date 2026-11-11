// background.ts
/// <reference types="chrome"/>

console.log("Manga Translator Service Worker started");

const BACKEND_URL = "http://127.0.0.1:8791";

// Ping health check to verify backend connection
async function checkBackendHealth() {
  try {
    const response = await fetch(`${BACKEND_URL}/health`);
    if (response.ok) {
      const data = await response.json();
      console.log("Backend health:", data);
      return true;
    }
  } catch (error) {
    console.warn("Backend is not reachable at", BACKEND_URL);
    return false;
  }
  return false;
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((request: any, sender: chrome.runtime.MessageSender, sendResponse: (response?: any) => void) => {
  if (request.action === "checkBackend") {
    checkBackendHealth().then(sendResponse);
    return true; // Indicates async response
  }
  
  if (request.action === "processImage") {
    processImageWithBackend(request.imageData).then(sendResponse);
    return true;
  }
});

async function processImageWithBackend(imageData: string) {
  try {
    // Chuyển đổi base64 sang blob để gửi đi
    const response = await fetch(imageData);
    const blob = await response.blob();
    
    const formData = new FormData();
    formData.append("image", blob, "image.png");
    formData.append("lang_src", "ja"); // Mặc định là JA, sau này có thể cấu hình
    
    const res = await fetch(`${BACKEND_URL}/pages/process`, {
        method: 'POST',
        body: formData
    });
    
    return await res.json();
  } catch (error) {
    console.error("Error processing image:", error);
    return { error: "Failed to process image" };
  }
}

// Periodic check
setInterval(checkBackendHealth, 30000);
checkBackendHealth();
