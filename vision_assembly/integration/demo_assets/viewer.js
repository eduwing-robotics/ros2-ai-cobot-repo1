"use strict";
const viewport = document.getElementById("viewport");
const picture = document.getElementById("report-image");
const slider = document.getElementById("zoom");
const zoomValue = document.getElementById("zoom-value");
let actualSize = false;
function applyZoom() {
  if (actualSize && picture.naturalWidth) {
    picture.style.width = picture.naturalWidth + "px";
    zoomValue.textContent = "원본 1:1";
  } else {
    const percent = Number(slider.value);
    picture.style.width = percent + "%";
    zoomValue.textContent = percent + "%";
  }
}
slider.addEventListener("input", () => { actualSize = false; applyZoom(); });
document.getElementById("fit").addEventListener("click", () => {
  actualSize = false; slider.value = "100"; applyZoom();
  viewport.scrollTo({ left: 0, top: 0 });
});
document.getElementById("actual").addEventListener("click", () => { actualSize = true; applyZoom(); });
picture.addEventListener("load", applyZoom);
const search = document.getElementById("search");
const rows = Array.from(document.querySelectorAll("tr.finding"));
search.addEventListener("input", () => {
  const query = search.value.trim().toLocaleLowerCase();
  let shown = 0;
  rows.forEach(row => {
    row.hidden = !row.textContent.toLocaleLowerCase().includes(query);
    if (!row.hidden) shown += 1;
  });
  document.getElementById("finding-count").textContent = shown + (query ? " / " + rows.length : "");
  document.getElementById("no-match").hidden = !query || shown !== 0;
  document.getElementById("filter-status").textContent = query ? "검출 목록 " + rows.length + "개 중 " + shown + "개 표시 · 이미지와 원본 판정은 변경되지 않습니다." : "";
});
applyZoom();
