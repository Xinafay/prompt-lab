import type { ValidatorDefinition } from "../types";
import { ValidatorsPreview } from "./ValidatorsPreview";

interface ValidatorsViewProps {
  validators: ValidatorDefinition[];
}

export function ValidatorsView({ validators }: ValidatorsViewProps) {
  return (
    <section className="overview-section overview-section-wide" aria-label="Validators">
      <div className="section-heading">
        <h3>Validators</h3>
        <span>{validators.length}</span>
      </div>
      <ValidatorsPreview validators={validators} />
    </section>
  );
}
