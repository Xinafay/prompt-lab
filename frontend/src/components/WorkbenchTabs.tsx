import { type WorkbenchTab, workbenchTabs } from "../urlState";

interface WorkbenchTabsProps {
  activeTab: WorkbenchTab;
  onTabChange: (tab: WorkbenchTab) => void;
}

const tabLabels: Record<WorkbenchTab, string> = {
  prompt: "Prompt",
  settings: "Settings",
  validators: "Validators",
  cases: "Cases",
  runs: "Runs",
  validation: "Validation",
  review: "Review",
  proposal: "Proposal",
  compare: "Compare"
};

const tabs: Array<{ id: WorkbenchTab; label: string }> = workbenchTabs.map(
  (tab) => ({ id: tab, label: tabLabels[tab] })
);

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
