// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type DataTableColumn } from "./DataTable";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

type Row = { id: string; name: string; count: number };
const rows: Row[] = Array.from({ length: 23 }, (_, i) => ({ id: `r${i + 1}`, name: `Item ${String.fromCharCode(65 + (i % 26))}${i + 1}`, count: (i * 7) % 11 }));
const columns: DataTableColumn<Row>[] = [
  { key: "name", header: "Name", sortValue: (r) => r.name, cell: (r) => r.name },
  { key: "count", header: "Count", sortValue: (r) => r.count, cell: (r) => String(r.count) },
];

const bodyRows = () => within(screen.getByRole("table", { name: "Things" })).getAllByRole("row").slice(1);

describe("DataTable", () => {
  it("pages the rows and says which ones are shown", () => {
    render(<DataTable label="Things" itemName="things" columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(bodyRows()).toHaveLength(10);
    expect(screen.getByText(/Showing/)).toHaveTextContent("Showing 1–10 of 23 things");
    fireEvent.click(screen.getByRole("button", { name: "Page 3" }));
    expect(bodyRows()).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "25" } });
    expect(bodyRows()).toHaveLength(23);
  });

  it("sorts by a column, then reverses it", () => {
    render(<DataTable label="Things" columns={columns} rows={rows} rowKey={(r) => r.id} />);
    fireEvent.click(screen.getByRole("button", { name: /Count/ }));
    expect(screen.getByRole("columnheader", { name: /Count/ })).toHaveAttribute("aria-sort", "ascending");
    expect(within(bodyRows()[0]).getAllByRole("cell")[1]).toHaveTextContent("0");
    fireEvent.click(screen.getByRole("button", { name: /Count/ }));
    expect(screen.getByRole("columnheader", { name: /Count/ })).toHaveAttribute("aria-sort", "descending");
    expect(within(bodyRows()[0]).getAllByRole("cell")[1]).toHaveTextContent("10");
  });

  it("opens a row from its link or a click anywhere on it", () => {
    render(<DataTable label="Things" columns={columns} rows={rows.slice(0, 2)} rowKey={(r) => r.id} rowHref={(r) => `/things/${r.id}`} />);
    expect(screen.getByRole("link", { name: "Item A1" })).toHaveAttribute("href", "/things/r1");
    fireEvent.click(within(bodyRows()[1]).getAllByRole("cell")[1]);
    expect(push).toHaveBeenCalledWith("/things/r2");
  });

  it("shows the empty state instead of rows and pager", () => {
    render(<DataTable label="Things" columns={columns} rows={[]} rowKey={(r) => r.id} empty={<p>No things yet</p>} />);
    expect(screen.getByText("No things yet")).toBeInTheDocument();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
  });
});
