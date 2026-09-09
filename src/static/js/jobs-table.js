(() => {
  const count = document.querySelector("#job-count");
  const error = document.querySelector("#jobs-error");
  const search = document.querySelector("#job-search");
  const refresh = document.querySelector("#refresh-jobs");
  const selectionCount = document.querySelector("#selection-count");
  const bulkStatus = document.querySelector("#bulk-status");
  const bulkDelete = document.querySelector("#bulk-delete");
  const bulkExport = document.querySelector("#bulk-export");
  const bulkMessage = document.querySelector("#bulk-message");
  const tableElement = document.querySelector("#jobs-table");
  const statusOptions = JSON.parse(tableElement.dataset.statusOptions || "[]");

  const setBulkMessage = (text, isError = false) => {
    if (!bulkMessage) {
      return;
    }
    bulkMessage.textContent = text;
    bulkMessage.classList.toggle("error-message", isError);
  };

  const table = new Tabulator("#jobs-table", {
    ajaxURL: "/api/jobs",
    ajaxResponse: (_url, _params, response) => {
      count.textContent = `${response.length} ${response.length === 1 ? "job" : "jobs"}`;
      error.hidden = true;
      return response;
    },
    ajaxError: () => {
      count.textContent = "Unable to load jobs";
      error.textContent = "The database could not be loaded. Try refreshing the page.";
      error.hidden = false;
    },
    layout: "fitColumns",
    placeholder: "No stored jobs yet.",
    pagination: true,
    paginationMode: "local",
    paginationSize: 25,
    paginationSizeSelector: [10, 25, 50, 100],
    selectableRows: true,
    initialSort: [
      { column: "seniority_match_score", dir: "desc" },
      { column: "scraped_at", dir: "desc" },
    ],
    columns: [
      { formatter: "rowSelection", titleFormatter: "rowSelection", titleFormatterParams: { rowRange: "active" }, width: 40, headerSort: false, cellClick: (e) => e.stopPropagation() },
      { title: "Title", field: "title", minWidth: 220, headerFilter: "input" },
      { title: "Company", field: "company", minWidth: 150, headerFilter: "input" },
      { title: "Location", field: "location", minWidth: 130, headerFilter: "input" },
      {
        title: "Status",
        field: "status",
        width: 130,
        headerFilter: "list",
        headerFilterParams: { valuesLookup: true, clearable: true },
        editor: "list",
        editorParams: { values: statusOptions, clearable: false },
        tooltip: "Click to edit status",
      },
      { title: "Type", field: "job_type", width: 115, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
      { title: "Experience", field: "experience_level", minWidth: 140, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
      { title: "Date Scraped", field: "scraped_at", width: 140, sorter: "string", formatter: (cell) => {
          const value = cell.getValue();
          return value ? new Date(value).toLocaleString() : "—";
        } },
      { title: "Seniority", field: "seniority_match_score", width: 90, hozAlign: "right", sorter: "number", sorterParams: { alignEmptyValues: "bottom" }, formatter: (cell) => {
          const value = cell.getValue();
          return value === null || value === undefined ? "—" : String(value);
        } },
      {
        title: "",
        field: "id",
        width: 115,
        headerSort: false,
        formatter: (cell) => `<a class="table-detail-link" href="/jobs/${cell.getValue()}">View details</a>`,
      },
    ],
  });

  const updateSelectionCount = () => {
    const selected = table.getSelectedRows().length;
    selectionCount.textContent = selected === 0
      ? "No rows selected"
      : `${selected} ${selected === 1 ? "row" : "rows"} selected`;
  };

  table.on("rowSelectionChanged", updateSelectionCount);
  table.on("dataLoaded", updateSelectionCount);

  const selectedIds = () => table.getSelectedData().map((row) => row.id);

  // Flow 1: inline per-row status editing — change saves immediately.
  table.on("cellEdited", async (cell) => {
    if (cell.getField() !== "status") {
      return;
    }
    const rowId = cell.getRow().getData().id;
    const newStatus = cell.getValue();
    try {
      const response = await fetch(`/api/jobs/${rowId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${response.status})`);
      }
      setBulkMessage(`Job #${rowId} status saved as ${newStatus}.`);
    } catch (requestError) {
      cell.restoreOldValue();
      setBulkMessage(`Could not save status: ${requestError.message}`, true);
    }
  });

  const applyBulkStatus = async (ids, status) => {
    const response = await fetch("/api/jobs/bulk-status", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_ids: ids, status }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Request failed (${response.status})`);
    }
    return response.json();
  };

  // Flow 2: toolbar dropdown auto-applies to selected rows on change.
  bulkStatus.addEventListener("change", async () => {
    const status = bulkStatus.value;
    if (!status) {
      return;
    }
    const ids = selectedIds();
    if (ids.length === 0) {
      setBulkMessage("Select at least one row to update status.", true);
      bulkStatus.value = "";
      return;
    }
    setBulkMessage(`Updating ${ids.length} ${ids.length === 1 ? "job" : "jobs"}…`);
    try {
      const result = await applyBulkStatus(ids, status);
      setBulkMessage(`Updated ${result.updated} of ${result.requested} jobs to ${result.status}.`);
      await table.replaceData();
    } catch (requestError) {
      setBulkMessage(`Could not update status: ${requestError.message}`, true);
    } finally {
      bulkStatus.value = "";
    }
  });

  const applySearch = () => {
    const term = search.value.trim().toLowerCase();
    if (!term) {
      table.clearFilter(false);
      return;
    }
    table.setFilter((job) => [job.title, job.company, job.location]
      .some((value) => value.toLowerCase().includes(term)));
  };

  search.addEventListener("input", applySearch);
  refresh.addEventListener("click", () => table.replaceData());

  bulkDelete.addEventListener("click", async () => {
    const ids = selectedIds();
    if (ids.length === 0) {
      setBulkMessage("Select at least one row to delete.", true);
      return;
    }
    if (!window.confirm(`Delete ${ids.length} selected ${ids.length === 1 ? "job" : "jobs"}?`)) {
      return;
    }
    setBulkMessage(`Deleting ${ids.length} ${ids.length === 1 ? "job" : "jobs"}…`);
    try {
      const response = await fetch("/api/jobs/bulk-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: ids }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${response.status})`);
      }
      const result = await response.json();
      setBulkMessage(`Deleted ${result.deleted} of ${result.requested} jobs.`);
      await table.replaceData();
    } catch (requestError) {
      setBulkMessage(`Could not delete jobs: ${requestError.message}`, true);
    }
  });

  bulkExport.addEventListener("click", async () => {
    const ids = selectedIds();
    const query = ids.length > 0 ? `?ids=${ids.join(",")}` : "";
    setBulkMessage(ids.length > 0 ? `Exporting ${ids.length} selected jobs…` : "Exporting all jobs…");
    try {
      const response = await fetch(`/api/jobs/export${query}`);
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${response.status})`);
      }
      const payload = await response.blob();
      const url = window.URL.createObjectURL(payload);
      const link = document.createElement("a");
      link.href = url;
      link.download = "jobs-export.json";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setBulkMessage(ids.length > 0 ? `Exported ${ids.length} jobs.` : "Exported all jobs.");
    } catch (requestError) {
      setBulkMessage(`Could not export jobs: ${requestError.message}`, true);
    }
  });
})();
