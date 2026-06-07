export type WorkbenchTab =
  | "overview"
  | "cases"
  | "runs"
  | "review"
  | "proposal"
  | "compare";

interface WorkbenchTabsProps {
  activeTab: WorkbenchTab;
  onTabChange: (tab: WorkbenchTab) => void;
}

const tabs: Array<{ id: WorkbenchTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "cases", label: "Cases" },
  { id: "runs", label: "Runs" },
  { id: "review", label: "Review" },
  { id: "proposal", label: "Proposal" },
  { id: "compare", label: "Compare" }
];

export function WorkbenchTabs({ activeTab, onTabChange }: WorkbenchTabsProps) {
  return (
    <div className="workbench-tabs" role="tablist" aria-label="Workbench sections">
      {tabs.map((tab) => (
        <button
          aria-selected={activeTab === tab.id}
          className={
            activeTab === tab.id ? "workbench-tab is-active" : "workbench-tab"
          }
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          role="tab"
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
