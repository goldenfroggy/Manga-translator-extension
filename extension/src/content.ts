// content.ts
console.log("Manga Translator Content Script loaded");

// Tối ưu observer để tránh spam
let debounceTimer: ReturnType<typeof setTimeout>;
const observer = new MutationObserver(() => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(findMangaImages, 500);
});

observer.observe(document.body, { childList: true, subtree: true });

function findMangaImages() {
  const images = Array.from(document.querySelectorAll("img"));
  const mangaImages = images.filter((img) => {
    const rect = img.getBoundingClientRect();
    return rect.width >= 400 && rect.height >= 500;
  });

  mangaImages.forEach(img => createTranslateButton(img));
}

// Thêm một nút nổi "Dịch" (Lever style)
function createTranslateButton(imgElement: HTMLImageElement) {
    if (imgElement.dataset.hasTranslateButton) return;
    imgElement.dataset.hasTranslateButton = "true";

    const button = document.createElement("button");
    button.innerText = "Dịch";
    button.style.position = "absolute";
    button.style.top = "10px";
    button.style.right = "10px";
    button.style.zIndex = "1000";
    button.style.backgroundColor = "green";
    button.style.color = "white";
    button.style.padding = "5px 10px";
    button.style.cursor = "pointer";
    
    // Wrapper để đặt nút lên trên ảnh
    const wrapper = document.createElement("div");
    wrapper.style.position = "relative";
    imgElement.parentNode?.insertBefore(wrapper, imgElement);
    wrapper.appendChild(imgElement);
    wrapper.appendChild(button);

    button.addEventListener("click", async () => {
        console.log("Đang dịch...", imgElement.src);
        const base64 = await getBase64FromImage(imgElement);
        // Gửi sang background để gọi backend
        chrome.runtime.sendMessage({ 
            action: "processImage", 
            imageData: base64 
        }, (response) => {
            console.log("Kết quả từ backend:", response);
        });
    });
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
