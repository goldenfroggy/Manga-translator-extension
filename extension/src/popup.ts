// popup.ts
/// <reference types="chrome"/>

const btn = document.getElementById("translate") as HTMLButtonElement;
const statusEl = document.getElementById("status")!;
const resultsEl = document.getElementById("results")!;

function setStatus(text: string, isError = false) {
  statusEl.textContent = text;
  statusEl.className = isError ? "err" : "";
}

function showResult(text: string, ok: boolean) {
  const div = document.createElement("div");
  div.className = `result ${ok ? "ok" : "err"}`;
  div.textContent = text;
  resultsEl.appendChild(div);
}

btn.addEventListener("click", async () => {
  resultsEl.innerHTML = "";
  setStatus("Đang tìm ảnh truyện...");
  btn.disabled = true;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      setStatus("Không xác định được tab.", true);
      return;
    }

    // 1. Yêu cầu content script thu thập ảnh (đã convert base64)
    const resp: { images: string[] } | undefined = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tab.id!, { action: "collectImages" }, (r) => {
        if (chrome.runtime.lastError) {
          console.warn(chrome.runtime.lastError.message);
          resolve(undefined);
        } else {
          resolve(r);
        }
      });
    });

    if (!resp || !resp.images || resp.images.length === 0) {
      setStatus("Không tìm thấy ảnh truyện nào trên trang này.", true);
      return;
    }

    // 2. Gửi từng ảnh tới backend qua service worker
    let done = 0;
    for (const imageData of resp.images) {
      setStatus(`Đang dịch ảnh ${done + 1}/${resp.images.length}...`);
      const result = await new Promise<any>((resolve) => {
        chrome.runtime.sendMessage({ action: "processImage", imageData }, (r) => {
          if (chrome.runtime.lastError) {
            resolve({ error: chrome.runtime.lastError.message });
          } else {
            resolve(r);
          }
        });
      });
      const index = done; // thứ tự khớp collectImages
      done++;
      if (result?.error) {
        showResult(`Ảnh ${done}: lỗi — ${result.error}`, false);
      } else if (result?.regions) {
        const n = result.regions.length;
        const translated = result.regions.filter((r: any) => r.vi_text).length;
        showResult(`Ảnh ${done}: ${n} vùng (${translated} có dịch)${result.cached ? " — cache" : ""}.`, true);
        // Yêu cầu content script vẽ overlay lên ảnh
        chrome.tabs.sendMessage(tab.id!, { action: "renderResult", index, result }, () => {
          if (chrome.runtime.lastError) console.warn(chrome.runtime.lastError.message);
        });
      } else {
        showResult(`Ảnh ${done}: phản hồi không rõ.`, false);
      }
    }

    setStatus(`Hoàn tất ${done}/${resp.images.length} ảnh.`);
  } catch (e: any) {
    setStatus(`Lỗi: ${e.message}`, true);
  } finally {
    btn.disabled = false;
  }
});
