import type { ValidatorDefinition } from "../types";
import { ValidatorCard } from "./ValidatorCard";

interface ValidatorsPreviewProps {
  validators: ValidatorDefinition[];
}

export function ValidatorsPreview({ validators }: ValidatorsPreviewProps) {
  return (
    <div className="validators-preview">
      {validators.length === 0 ? (
        <div className="empty-state compact-empty-state">
          <h2>No validators configured</h2>
          <p>Add validators before running validation.</p>
        </div>
      ) : (
        validators.map((validator) => (
          <ValidatorCard
            key={validator.validator_id}
            showActions={false}
            validator={validator}
          />
        ))
      )}
    </div>
  );
}
