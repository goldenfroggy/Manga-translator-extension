// content.ts
console.log("Manga Translator Content Script loaded");

interface RegionResult {
  id: number;
  order: number;
  bbox: [number, number, number, number];
  src_text: string;
  vi_text: string;
  kind: string;
  score: number;
  text_color: string | null;
  bg_color: string | null;
}

interface PageResult {
  page_id: string;
  size: [number, number];
  regions: RegionResult[];
  patches: { bbox: [number, number, number, number]; png_b64: string }[];
  timing_ms: Record<string, number>;
  engine: string;
  cached?: boolean;
}

// Danh sách ảnh truyện hiện có (được cập nhật liên tục)
let mangaImages: HTMLImageElement[] = [];
const overlayLayers = new Set<HTMLDivElement>();

// Tối ưu observer để tránh spam
let debounceTimer: ReturnType<typeof setTimeout>;
const observer = new MutationObserver(() => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(findMangaImages, 500);
});

observer.observe(document.body, { childList: true, subtree: true });

function findMangaImages() {
  const images = Array.from(document.querySelectorAll("img"));
  mangaImages = images.filter((img) => {
    const rect = img.getBoundingClientRect();
    return rect.width >= 400 && rect.height >= 500 && img.complete && img.naturalWidth > 0;
  });
}

// Nhận yêu cầu từ popup
chrome.runtime.onMessage.addListener(
  (request: any, _sender: chrome.runtime.MessageSender, sendResponse: (response?: any) => void) => {
    if (request.action === "collectImages") {
      findMangaImages(); // cập nhật danh sách mới nhất
      const limit = mangaImages.slice(0, 10); // giới hạn 10 ảnh/lượt
      Promise.all(limit.map(getBase64FromImage))
        .then((images) => sendResponse({ images }))
        .catch((e) => {
          console.error("collectImages lỗi:", e);
          sendResponse({ images: [] });
        });
      return true; // async
    }

    if (request.action === "renderResult") {
      const { index, result } = request as { index: number; result: PageResult };
      findMangaImages();
      const img = mangaImages[index];
      if (!img) {
        console.warn(`renderResult: không tìm thấy ảnh ${index}`);
        sendResponse({ ok: false });
      } else {
        renderOverlay(img, result);
        sendResponse({ ok: true });
      }
      return true;
    }
  }
);

// ===== Overlay (doc 06 §4): patch sạch trước, rồi chữ Việt =====
function renderOverlay(img: HTMLImageElement, result: PageResult) {
  // Bọc ảnh trong wrapper relative (idempotent)
  let wrapper = img.parentElement;
  if (!wrapper || !wrapper.dataset.mtaWrapper) {
    wrapper = document.createElement("div");
    wrapper.dataset.mtaWrapper = "1";
    wrapper.style.position = "relative";
    img.parentNode?.insertBefore(wrapper, img);
    wrapper.appendChild(img);
  }

  // Xoá layer cũ (dịch lại)
  wrapper.querySelectorAll(".mta-layer").forEach((e) => {
    overlayLayers.delete(e as HTMLDivElement);
    e.remove();
  });

  const [origW, origH] = result.size;
  const sx = img.clientWidth / origW; // tỉ lệ hiển thị / gốc
  const sy = img.clientHeight / origH;

  const layer = document.createElement("div");
  layer.className = "mta-layer";
  layer.style.position = "absolute";
  layer.style.left = "0";
  layer.style.top = "0";
  layer.style.width = "100%";
  layer.style.height = "100%";
  layer.style.pointerEvents = "none";
  layer.style.overflow = "hidden";
  wrapper.appendChild(layer);
  overlayLayers.add(layer);

  // 1. Patch sạch đè lên vùng chữ gốc
  for (const patch of result.patches) {
    const [x1, y1, x2, y2] = patch.bbox;
    const el = document.createElement("div");
    el.style.position = "absolute";
    el.style.left = `${x1 * sx}px`;
    el.style.top = `${y1 * sy}px`;
    el.style.width = `${(x2 - x1) * sx}px`;
    el.style.height = `${(y2 - y1) * sy}px`;
    el.style.backgroundSize = "100% 100%";

    if (patch.png_b64) {
      el.style.backgroundImage = `url(data:image/png;base64,${patch.png_b64})`;
    } else {
      // patch encode lỗi → dùng màu nền ước lượng
      el.style.background = "#fff";
    }
    layer.appendChild(el);
  }

  // 2. Chữ Việt đè lên patch
  for (const region of result.regions) {
    if (!region.vi_text) continue; // LLM lỗi/không cấu hình → chỉ patch sạch
    const [x1, y1, x2, y2] = region.bbox;
    const el = document.createElement("div");
    el.style.position = "absolute";
    el.style.left = `${x1 * sx}px`;
    el.style.top = `${y1 * sy}px`;
    el.style.width = `${(x2 - x1) * sx}px`;
    el.style.height = `${(y2 - y1) * sy}px`;
    el.style.display = "flex";
    el.style.alignItems = "center";
    el.style.justifyContent = "center";
    el.style.padding = "2px";
    el.style.boxSizing = "border-box";
    el.style.overflow = "hidden";
    el.style.textAlign = "center";
    // Màu chữ: phải tương phản với nền bong bóng (bg_color ước lượng);
    // nếu kém tương phản → chọn đen/trắng theo độ sáng nền
    const bg = parseHex(region.bg_color) ?? { r: 255, g: 255, b: 255 };
    let text = parseHex(region.text_color);
    if (!text || contrast(text, bg) < 3) {
      text = luminance(bg) > 0.5 ? { r: 17, g: 17, b: 17 } : { r: 255, g: 255, b: 255 };
    }
    el.style.color = rgbToCss(text);
    // Patch sạch đã là nền → KHÔNG vẽ hộp màu (tránh lộ ô xám).
    // Chỉ dùng màu nền khi patch thiếu (encode lỗi).
    const hasPatch = !!result.patches.find((p) => {
      const [px1, py1, px2, py2] = p.bbox;
      return px1 <= x1 && py1 <= y1 && px2 >= x2 && py2 >= y2 && p.png_b64;
    });
    if (!hasPatch) {
      el.style.backgroundColor = rgbToCss(bg);
    }
    el.style.lineHeight = "1.15";
    el.style.fontFamily = "system-ui, sans-serif";
    el.style.fontWeight = "600";
    el.style.whiteSpace = "pre-wrap";
    el.style.wordBreak = "break-word";
    el.textContent = region.vi_text;

    // Auto-fit: bắt đầu từ 35% chiều cao bbox, thu dần tới khi vừa khung
    let fs = Math.max(8, (y2 - y1) * sy * 0.35);
    el.style.fontSize = `${fs}px`;
    while (fs > 8 && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)) {
      fs -= 1;
      el.style.fontSize = `${fs}px`;
    }

    // Viền vàng khi OCR tin cậy thấp (doc 06 §4)
    if (region.kind === "ocr_low") {
      el.style.outline = "2px solid rgba(255, 200, 0, 0.8)";
    }
    layer.appendChild(el);
  }

  console.log(`Overlay: ${result.patches.length} patch, ${result.regions.length} vùng (${result.timing_ms?.total_ms ?? "?"}ms)`);
}

// Phím tắt: giữ Alt = xem gốc
document.addEventListener("keydown", (e) => {
  if (e.key === "Alt") overlayLayers.forEach((l) => (l.style.opacity = "0"));
});
document.addEventListener("keyup", (e) => {
  if (e.key === "Alt") overlayLayers.forEach((l) => (l.style.opacity = "1"));
});

// ===== Helpers màu (so sánh tương phản chữ/nền) =====
function parseHex(h: string | null): { r: number; g: number; b: number } | null {
  if (!h || !h.startsWith("#")) return null;
  const n = parseInt(h.slice(1), 16);
  if (Number.isNaN(n) || h.length !== 7) return null;
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

function luminance(c: { r: number; g: number; b: number }): number {
  return (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) / 255;
}

function contrast(
  a: { r: number; g: number; b: number },
  b: { r: number; g: number; b: number }
): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

function rgbToCss(c: { r: number; g: number; b: number }): string {
  return `rgb(${c.r},${c.g},${c.b})`;
}

// Helper: Convert image to Base64
async function getBase64FromImage(imgElement: HTMLImageElement): Promise<string> {
  const response = await fetch(imgElement.src);
  const blob = await response.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
