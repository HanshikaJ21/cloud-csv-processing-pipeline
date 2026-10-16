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
const processingMode = document.querySelector("#processing-mode");
const sizeLimit = document.querySelector("#size-limit");
const privacyNote = document.querySelector("#privacy-note");
const footerNotice = document.querySelector("#footer-notice");
const footerMode = document.querySelector("#footer-mode");

let maxBytes = 5 * 1024 * 1024;
let selectedFile = null;
let cleanedCsv = "";
let processorReady = false;

function formatBytes(bytes) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KiB`
    : `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
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
  processButton.disabled = !processorReady;
  resetResult();
  if (!file.name.toLowerCase().endsWith(".csv")) {
    showError("Please choose a file with a .csv extension.");
  } else if (file.size > maxBytes) {
    showError(`This file is larger than the ${formatBytes(maxBytes)} size limit.`);
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

async function loadProcessorInfo() {
  try {
    const response = await fetch("/api/info", { headers: { Accept: "application/json" } });
    const info = await response.json();
    if (!response.ok || typeof info.max_input_bytes !== "number") {
      throw new Error("Processor information is unavailable.");
    }
    maxBytes = info.max_input_bytes;
    const local = info.mode === "local";
    processingMode.textContent = local ? "LOCAL PROCESSING" : "VERCEL PROCESSING";
    footerMode.textContent = local ? "LOCAL DEMO" : "HOSTED DEMO";
    sizeLimit.textContent = `Up to ${formatBytes(maxBytes)}`;
    privacyNote.textContent = local
      ? "Your file is sent only to the processor on this device. It is not uploaded to AWS."
      : "Your file is sent to Vercel for processing. Do not use sensitive or confidential data.";
    footerNotice.textContent = local
      ? "Decimal-accurate calculations. Processing stays on this device."
      : "Decimal-accurate calculations. Files are sent to Vercel and not saved by this app.";
    processorReady = true;
    processButton.disabled = !selectedFile;
  } catch {
    processingMode.textContent = "PROCESSOR UNAVAILABLE";
    footerMode.textContent = "UNAVAILABLE";
    privacyNote.textContent = "Cannot verify the processor. Reload before selecting a file.";
    footerNotice.textContent = "The processor could not be verified.";
    processorReady = false;
    processButton.disabled = true;
  }
}

loadProcessorInfo();

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
  if (!processorReady) {
    showError("The processor is unavailable. Reload the page and try again.");
    return;
  }
  if (!selectedFile.name.toLowerCase().endsWith(".csv") || selectedFile.size > maxBytes) {
    showError(selectedFile.size > maxBytes
      ? `This file is larger than the ${formatBytes(maxBytes)} size limit.`
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
    showError("Could not reach the processor. Check your connection and try again.");
  } finally {
    processButton.disabled = !selectedFile || !processorReady;
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
