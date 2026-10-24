export interface BlueprintTypeConfig {
  enabled: boolean;
  count: number;
  marks: number;
}

export type BlueprintState = {
  mcq: BlueprintTypeConfig;
  true_false: BlueprintTypeConfig;
  fill_blank: BlueprintTypeConfig;
  short_answer: BlueprintTypeConfig;
  long_answer: BlueprintTypeConfig;
};

export const ALL_QUESTION_TYPES: (keyof BlueprintState)[] = [
  "mcq",
  "true_false",
  "fill_blank",
  "short_answer",
  "long_answer",
];

export const BASE_WEIGHTS: Record<keyof BlueprintState, number> = {
  mcq: 0.2,
  true_false: 0.1,
  fill_blank: 0.1,
  short_answer: 0.25,
  long_answer: 0.35,
};

export const BASE_MARKS_PER_QUESTION: Record<keyof BlueprintState, number> = {
  mcq: 2,
  true_false: 2,
  fill_blank: 2,
  short_answer: 5,
  long_answer: 10,
};

export const PRESET_WEIGHTS: Record<string, Record<keyof BlueprintState, number>> = {
  mixed: {
    mcq: 0.2,
    true_false: 0.1,
    fill_blank: 0.1,
    short_answer: 0.25,
    long_answer: 0.35,
  },
  objective: {
    mcq: 0.4,
    true_false: 0.3,
    fill_blank: 0.3,
    short_answer: 0.0,
    long_answer: 0.0,
  },
  subjective: {
    mcq: 0.0,
    true_false: 0.0,
    fill_blank: 0.0,
    short_answer: 0.4,
    long_answer: 0.6,
  },
};

export function computeBlueprintTotal(blueprint: BlueprintState): number {
  if (!blueprint) return 0;
  let total = 0;
  for (const key of ALL_QUESTION_TYPES) {
    const cfg = blueprint[key];
    if (cfg && cfg.enabled) {
      const count = Math.max(0, Math.floor(cfg.count || 0));
      const marks = Math.max(1, Math.floor(cfg.marks || 1));
      total += count * marks;
    }
  }
  return total;
}

export function allocateBlueprintToTarget(
  targetMarks: number,
  enabledTypes?: (keyof BlueprintState)[],
  preset?: "mixed" | "objective" | "subjective"
): { blueprint: BlueprintState; notes: string[] } {
  const target = Math.max(1, Math.floor(targetMarks));
  const notes: string[] = [];

  let selectedTypes: (keyof BlueprintState)[];
  let weightsMap: Record<keyof BlueprintState, number>;

  if (preset && PRESET_WEIGHTS[preset]) {
    weightsMap = PRESET_WEIGHTS[preset];
    selectedTypes = ALL_QUESTION_TYPES.filter((t) => weightsMap[t] > 0);
  } else {
    weightsMap = BASE_WEIGHTS;
    if (enabledTypes && enabledTypes.length > 0) {
      selectedTypes = enabledTypes.filter((t) => ALL_QUESTION_TYPES.includes(t));
    } else {
      selectedTypes = [...ALL_QUESTION_TYPES];
    }
  }

  if (!selectedTypes.length) {
    selectedTypes = ["mcq"];
    notes.push("No valid question types enabled; defaulted to MCQ.");
  }

  // Filter out types whose minimum marks exceed target
  let viableTypes: (keyof BlueprintState)[] = [];
  for (const t of selectedTypes) {
    const baseM = BASE_MARKS_PER_QUESTION[t];
    if (baseM <= target || (["mcq", "true_false", "fill_blank"].includes(t) && target >= 1)) {
      viableTypes.push(t);
    }
  }

  if (!viableTypes.length) {
    viableTypes = ["mcq"];
    notes.push(`Target of ${target} marks is too small for selected types. Selected MCQ with 1 mark.`);
  }

  if (viableTypes.length < selectedTypes.length) {
    const omitted = selectedTypes.filter((t) => !viableTypes.includes(t));
    notes.push(`Target marks (${target}) too low to include: ${omitted.join(", ")}.`);
  }

  // Determine initial marks per question
  const typeMarks: Partial<Record<keyof BlueprintState, number>> = {};
  for (const t of viableTypes) {
    if (target === 1 && ["mcq", "true_false", "fill_blank"].includes(t)) {
      typeMarks[t] = 1;
    } else if (target < BASE_MARKS_PER_QUESTION[t]) {
      typeMarks[t] = 1;
    } else {
      typeMarks[t] = BASE_MARKS_PER_QUESTION[t];
    }
  }

  // If target is odd, ensure at least one viable type has odd marks
  if (target % 2 === 1) {
    const hasOdd = viableTypes.some((t) => (typeMarks[t] || 2) % 2 === 1);
    if (!hasOdd) {
      const candidates: (keyof BlueprintState)[] = ["mcq", "fill_blank", "true_false"];
      for (const obj of candidates) {
        if (viableTypes.includes(obj)) {
          typeMarks[obj] = 1;
          notes.push(`Adjusted ${obj.replace("_", " ").toUpperCase()} to 1 mark to accommodate odd target.`);
          break;
        }
      }
    }
  }

  // Weights for viable types
  const getSubWeights = () => {
    const sw: Partial<Record<keyof BlueprintState, number>> = {};
    let sum = 0;
    for (const t of viableTypes) {
      const w = weightsMap[t] || 0.2;
      sw[t] = w;
      sum += w;
    }
    const nw: Partial<Record<keyof BlueprintState, number>> = {};
    for (const t of viableTypes) {
      nw[t] = (sw[t] || 0.2) / (sum || 1.0);
    }
    return nw;
  };

  let normWeights = getSubWeights();

  // Prune heavy types if min budget exceeds target
  let minBudget = viableTypes.reduce((acc, t) => acc + (typeMarks[t] || 1), 0);
  while (minBudget > target && viableTypes.length > 1) {
    // Find type with largest marks or lowest weight
    let remIdx = 0;
    let maxMark = -1;
    viableTypes.forEach((t, idx) => {
      const m = typeMarks[t] || 1;
      if (m > maxMark) {
        maxMark = m;
        remIdx = idx;
      }
    });
    const remType = viableTypes[remIdx];
    viableTypes.splice(remIdx, 1);
    delete typeMarks[remType];
    notes.push(`Target ${target} is too small to include ${remType.replace("_", " ")}; omitted to maintain valid blueprint.`);
    normWeights = getSubWeights();
    minBudget = viableTypes.reduce((acc, t) => acc + (typeMarks[t] || 1), 0);
  }

  // Give 1 question to each remaining viable type
  const counts: Partial<Record<keyof BlueprintState, number>> = {};
  for (const t of viableTypes) {
    counts[t] = 1;
  }

  let remainingMarks = target - viableTypes.reduce((acc, t) => acc + (counts[t] || 1) * (typeMarks[t] || 1), 0);

  if (remainingMarks > 0) {
    // Sort types by weight descending
    const sortedTypes = [...viableTypes].sort((a, b) => (normWeights[b] || 0) - (normWeights[a] || 0));
    for (const t of sortedTypes) {
      const mPerQ = typeMarks[t] || 1;
      const idealExtraMarks = remainingMarks * (normWeights[t] || 0);
      const idealExtraQ = Math.floor(idealExtraMarks / mPerQ);
      if (idealExtraQ > 0) {
        counts[t] = (counts[t] || 1) + idealExtraQ;
        remainingMarks -= idealExtraQ * mPerQ;
      }
    }

    // Greedy distribution of remaining marks
    while (remainingMarks > 0) {
      let allocatedAny = false;
      const sortedByMarksDesc = [...viableTypes].sort((a, b) => (typeMarks[b] || 1) - (typeMarks[a] || 1));
      for (const t of sortedByMarksDesc) {
        const mPerQ = typeMarks[t] || 1;
        if (mPerQ <= remainingMarks) {
          counts[t] = (counts[t] || 1) + 1;
          remainingMarks -= mPerQ;
          allocatedAny = true;
          break;
        }
      }
      if (!allocatedAny) {
        // Adjust an objective type to 1 mark to fit exact remaining marks
        let objFound = false;
        const candidates: (keyof BlueprintState)[] = ["mcq", "fill_blank", "true_false"];
        for (const obj of candidates) {
          if (viableTypes.includes(obj)) {
            const oldM = typeMarks[obj] || 2;
            if (oldM > 1) {
              typeMarks[obj] = 1;
              counts[obj] = (counts[obj] || 1) * oldM + remainingMarks;
              remainingMarks = 0;
              notes.push(`Adjusted ${obj.replace("_", " ").toUpperCase()} to 1 mark to fit exact target.`);
              objFound = true;
              break;
            }
          }
        }
        if (!objFound) {
          counts[viableTypes[0]] = (counts[viableTypes[0]] || 1) + 1;
          remainingMarks = 0;
        }
        break;
      }
    }
  }

  // Construct full 5-key blueprint
  const resultBlueprint: BlueprintState = {
    mcq: { enabled: false, count: 0, marks: BASE_MARKS_PER_QUESTION.mcq },
    true_false: { enabled: false, count: 0, marks: BASE_MARKS_PER_QUESTION.true_false },
    fill_blank: { enabled: false, count: 0, marks: BASE_MARKS_PER_QUESTION.fill_blank },
    short_answer: { enabled: false, count: 0, marks: BASE_MARKS_PER_QUESTION.short_answer },
    long_answer: { enabled: false, count: 0, marks: BASE_MARKS_PER_QUESTION.long_answer },
  };

  for (const t of ALL_QUESTION_TYPES) {
    if (viableTypes.includes(t)) {
      resultBlueprint[t] = {
        enabled: true,
        count: counts[t] || 1,
        marks: typeMarks[t] || BASE_MARKS_PER_QUESTION[t],
      };
    }
  }

  // Micro verification
  const actualSum = computeBlueprintTotal(resultBlueprint);
  if (actualSum !== target) {
    const diff = target - actualSum;
    const primary = viableTypes[0];
    const m = resultBlueprint[primary].marks;
    if (diff % m === 0) {
      resultBlueprint[primary].count += Math.floor(diff / m);
    } else {
      resultBlueprint[primary].marks = 1;
      const otherMarks = viableTypes
        .filter((k) => k !== primary)
        .reduce((acc, k) => acc + resultBlueprint[k].count * resultBlueprint[k].marks, 0);
      resultBlueprint[primary].count = target - otherMarks;
    }
  }

  return { blueprint: resultBlueprint, notes };
}

export function rebalanceBlueprintToTarget(
  currentBlueprint: BlueprintState,
  newTargetMarks: number
): { blueprint: BlueprintState; notes: string[] } {
  const target = Math.max(1, Math.floor(newTargetMarks));
  const enabledTypes = ALL_QUESTION_TYPES.filter((t) => currentBlueprint[t]?.enabled);
  if (!enabledTypes.length) {
    return allocateBlueprintToTarget(target);
  }
  return allocateBlueprintToTarget(target, enabledTypes);
}

export function balanceBlueprintSmallestChange(
  currentBlueprint: BlueprintState,
  targetMarks: number
): { blueprint: BlueprintState; explanation: string } {
  const target = Math.max(1, Math.floor(targetMarks));
  const currentTotal = computeBlueprintTotal(currentBlueprint);
  const diff = target - currentTotal;
  if (diff === 0) {
    return { blueprint: currentBlueprint, explanation: "Blueprint already matches target marks." };
  }

  const bp: BlueprintState = JSON.parse(JSON.stringify(currentBlueprint));
  const enabledTypes = ALL_QUESTION_TYPES.filter((t) => bp[t]?.enabled && bp[t].marks > 0);

  if (!enabledTypes.length) {
    const fresh = allocateBlueprintToTarget(target);
    return { blueprint: fresh.blueprint, explanation: `Configured blueprint for ${target} target marks.` };
  }

  // Attempt single type count adjustments
  for (const t of enabledTypes) {
    const m = bp[t].marks;
    const c = bp[t].count;
    if (diff > 0) {
      if (diff % m === 0) {
        const delta = Math.floor(diff / m);
        bp[t].count = c + delta;
        return {
          blueprint: bp,
          explanation: `Add ${delta} ${t.replace("_", " ")} question${delta > 1 ? "s" : ""} (+${diff} marks)`,
        };
      }
    } else {
      const absDiff = -diff;
      if (absDiff % m === 0) {
        const delta = Math.floor(absDiff / m);
        if (c - delta >= 1) {
          bp[t].count = c - delta;
          return {
            blueprint: bp,
            explanation: `Remove ${delta} ${t.replace("_", " ")} question${delta > 1 ? "s" : ""} (-${absDiff} marks)`,
          };
        }
      }
    }
  }

  // Proportional rebalance
  const rebalanced = rebalanceBlueprintToTarget(bp, target);
  return {
    blueprint: rebalanced.blueprint,
    explanation: `Rebalanced question counts across enabled types to equal ${target} marks.`,
  };
}

export const QUESTION_TIME_MINUTES: Record<keyof BlueprintState, number> = {
  mcq: 1.0,
  true_false: 1.0,
  fill_blank: 1.0,
  short_answer: 4.0,
  long_answer: 10.0,
};

export function estimateExamTime(blueprint: BlueprintState): number {
  if (!blueprint) return 0;
  let total = 0;
  for (const key of ALL_QUESTION_TYPES) {
    const cfg = blueprint[key];
    if (cfg && cfg.enabled && cfg.count > 0) {
      total += cfg.count * (QUESTION_TIME_MINUTES[key] || 1.0);
    }
  }
  return Math.round(total * 10) / 10;
}

