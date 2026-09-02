(() => {
  const count = document.querySelector("#job-count");
  const error = document.querySelector("#jobs-error");
  const search = document.querySelector("#job-search");
  const refresh = document.querySelector("#refresh-jobs");

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
      { column: "final_score", dir: "desc" },
      { column: "scraped_at", dir: "desc" },
    ],
    columns: [
      { title: "Title", field: "title", minWidth: 220, headerFilter: "input" },
      { title: "Company", field: "company", minWidth: 170, headerFilter: "input" },
      { title: "Location", field: "location", minWidth: 150, headerFilter: "input" },
      { title: "Type", field: "job_type", width: 125, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
      { title: "Experience", field: "experience_level", minWidth: 150, headerFilter: "list", headerFilterParams: { valuesLookup: true, clearable: true } },
      { title: "Date Scraped", field: "scraped_at", width: 140, sorter: "datetime", formatter: (cell) => {
          const value = cell.getValue();
          return value ? new Date(value).toLocaleString() : "—";
        } },
      { title: "Seniority", field: "seniority_match_score", width: 95, hozAlign: "right", sorter: "number", sorterParams: { alignEmptyValues: "bottom" }, formatter: (cell) => {
          const value = cell.getValue();
          return value === null || value === undefined ? "—" : String(value);
        } },
      { title: "CV match", field: "cv_match_score", width: 90, hozAlign: "right", sorter: "number", sorterParams: { alignEmptyValues: "bottom" }, formatter: (cell) => {
          const value = cell.getValue();
          return value === null || value === undefined ? "—" : Number(value).toFixed(2);
        } },
      { title: "Score", field: "final_score", width: 80, hozAlign: "right", sorter: "number", sorterParams: { alignEmptyValues: "bottom" }, formatter: (cell) => {
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
})();
