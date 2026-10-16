const form = document.querySelector("#upload-form");
const fileInput = document.querySelector("#file-input");
const dropZone = document.querySelector("#drop-zone");
const fileRow = document.querySelector("#file-row");
const fileName = document.querySelector("#file-name");
const fileSize = document.querySelector("#file-size");
const processButton = document.querySelector("#process-button");
const resultPanel = document.querySelector("#result-panel");
const resultTitle = document.querySelector("#result-title");
const resultStatus = document.querySelector("#result-status");
const resultContent = document.querySelector("#result-content");
const errorMessage = document.querySelector("#error-message");

const MAX_BYTES = 5 * 1024 * 1024;
let selectedFile = null;
let cleanedCsv = "";

function formatBytes(bytes) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function resetResult() {
  resultPanel.hidden = true;
  errorMessage.hidden = true;
  resultContent.hidden = false;
  cleanedCsv = "";
}

function selectFile(file) {
  if (!file) return;
  selectedFile = file;
  fileInput.value = "";
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  fileRow.hidden = false;
  processButton.disabled = false;
  resetResult();
  if (!file.name.toLowerCase().endsWith(".csv")) {
    showError("Please choose a file with a .csv extension.");
  } else if (file.size > MAX_BYTES) {
    showError("This file is larger than the 5 MiB size limit.");
  }
}

function showError(message) {
  resultPanel.hidden = false;
  resultTitle.textContent = "We couldn't process this file";
  resultStatus.textContent = "Rejected";
  resultStatus.classList.add("rejected");
  resultContent.hidden = true;
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));

document.querySelector("#remove-file").addEventListener("click", () => {
  selectedFile = null;
  fileRow.hidden = true;
  processButton.disabled = true;
  resetResult();
});

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
}

dropZone.addEventListener("drop", (event) => {
  selectFile(event.dataTransfer.files[0]);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedFile) return;
  if (!selectedFile.name.toLowerCase().endsWith(".csv") || selectedFile.size > MAX_BYTES) {
    showError(selectedFile.size > MAX_BYTES
      ? "This file is larger than the 5 MiB size limit."
      : "Please choose a file with a .csv extension.");
    return;
  }

  processButton.disabled = true;
  processButton.setAttribute("aria-busy", "true");
  processButton.textContent = "Processing…";
  resultPanel.hidden = true;

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: selectedFile,
    });
    const result = await response.json();
    if (!response.ok || result.status !== "success") {
      showError(result.error || "The file could not be processed.");
      return;
    }

    cleanedCsv = result.cleaned_csv;
    document.querySelector("#rows-processed").textContent = result.rows_processed;
    document.querySelector("#duplicates-removed").textContent = result.duplicates_removed;
    document.querySelector("#total-revenue").textContent = result.total_revenue;
    resultTitle.textContent = "Your file is ready";
    resultStatus.textContent = "Success";
    resultStatus.classList.remove("rejected");
    errorMessage.hidden = true;
    resultContent.hidden = false;
    resultPanel.hidden = false;
  } catch {
    showError("Could not reach the local processor. Check that it is running and try again.");
  } finally {
    processButton.disabled = !selectedFile;
    processButton.removeAttribute("aria-busy");
    processButton.innerHTML = 'Process file <span aria-hidden="true">→</span>';
  }
});

document.querySelector("#download-button").addEventListener("click", () => {
  if (!cleanedCsv) return;
  const blob = new Blob([cleanedCsv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const baseName = (selectedFile?.name || "cleaned").replace(/\.csv$/i, "");
  link.href = url;
  link.download = `${baseName}-processed.csv`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
});
