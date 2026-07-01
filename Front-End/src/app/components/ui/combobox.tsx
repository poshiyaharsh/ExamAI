"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { CheckIcon, ChevronDownIcon } from "lucide-react";

import { cn } from "./utils";

export type ComboboxOption = {
  value: string;
  label: string;
};

type ComboboxProps = {
  options: ComboboxOption[];
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  disabled?: boolean;
  className?: string;
};

type DropdownPosition = {
  top: number;
  left: number;
  width: number;
};

function Combobox({
  options,
  value,
  onValueChange,
  placeholder = "Select option",
  searchPlaceholder = "Search...",
  emptyText = "No departments found.",
  disabled = false,
  className,
}: ComboboxProps) {
  const wrapperRef = React.useRef<HTMLDivElement | null>(null);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const panelRef = React.useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [activeIndex, setActiveIndex] = React.useState(0);
  const [position, setPosition] = React.useState<DropdownPosition | null>(null);

  const selectedOption = React.useMemo(
    () => options.find((option) => option.value === value) ?? null,
    [options, value],
  );

  const filteredOptions = React.useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return options;
    }

    return options.filter((option) => option.label.toLowerCase().includes(normalizedQuery));
  }, [options, query]);

  const updatePosition = React.useCallback(() => {
    const inputElement = inputRef.current;
    if (!inputElement) {
      return;
    }

    const rect = inputElement.getBoundingClientRect();
    setPosition({
      top: rect.bottom + 4,
      left: rect.left,
      width: rect.width,
    });
  }, []);

  const openDropdown = React.useCallback(() => {
    if (disabled) {
      return;
    }

    setOpen(true);
    setActiveIndex(0);
    setQuery("");
    updatePosition();
  }, [disabled, updatePosition]);

  const closeDropdown = React.useCallback(() => {
    setOpen(false);
    setActiveIndex(0);
    setQuery("");
  }, []);

  const selectOption = React.useCallback(
    (option: ComboboxOption) => {
      onValueChange(option.value);
      setQuery("");
      setActiveIndex(0);
      setOpen(false);
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.setSelectionRange(0, 0);
      });
    },
    [onValueChange],
  );

  React.useEffect(() => {
    if (!open) {
      return;
    }

    updatePosition();

    const handlePointerDown = (event: MouseEvent | PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) {
        return;
      }

      if (wrapperRef.current?.contains(target) || panelRef.current?.contains(target)) {
        return;
      }

      closeDropdown();
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDropdown();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [closeDropdown, open, updatePosition]);

  React.useEffect(() => {
    if (!open) {
      return;
    }

    if (activeIndex >= filteredOptions.length) {
      setActiveIndex(filteredOptions.length > 0 ? filteredOptions.length - 1 : 0);
    }
  }, [activeIndex, filteredOptions.length, open]);

  React.useEffect(() => {
    if (!open) {
      return;
    }

    updatePosition();
  }, [filteredOptions, open, updatePosition]);

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const nextValue = event.target.value;
    if (!open) {
      setOpen(true);
    }
    setQuery(nextValue);
    setActiveIndex(0);
    updatePosition();
  };

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
      }
      setActiveIndex((currentIndex) => {
        if (!filteredOptions.length) {
          return 0;
        }
        return Math.min(currentIndex + 1, filteredOptions.length - 1);
      });
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
      }
      setActiveIndex((currentIndex) => Math.max(currentIndex - 1, 0));
      return;
    }

    if (event.key === "Enter") {
      if (!open) {
        setOpen(true);
        return;
      }

      event.preventDefault();
      const option = filteredOptions[activeIndex];
      if (option) {
        selectOption(option);
      }
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeDropdown();
    }
  };

  const inputDisplayValue = open ? (query ? query : selectedOption?.label ?? "") : selectedOption?.label ?? "";
  const isEmpty = filteredOptions.length === 0;

  const dropdown = open && position && typeof document !== "undefined"
    ? createPortal(
        <div
          ref={panelRef}
          className="pointer-events-auto absolute rounded-md border border-border bg-popover shadow-lg"
          style={{
            top: position.top,
            left: position.left,
            width: position.width,
            zIndex: 9999,
          }}
        >
          <div className="max-h-[220px] overflow-y-auto p-1">
            {isEmpty ? (
              <div className="px-3 py-2 text-sm text-muted-foreground">{emptyText}</div>
            ) : (
              filteredOptions.map((option, index) => {
                const isSelected = option.value === value;
                const isActive = index === activeIndex;

                return (
                  <button
                    key={option.value}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm outline-none transition-colors",
                      isActive || isSelected
                        ? "bg-accent text-accent-foreground"
                        : "text-foreground hover:bg-accent/70 hover:text-accent-foreground",
                    )}
                    onMouseEnter={() => setActiveIndex(index)}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => selectOption(option)}
                  >
                    <CheckIcon
                      className={cn(
                        "size-4 shrink-0",
                        isSelected ? "opacity-100" : "opacity-0",
                      )}
                    />
                    <span className="truncate">{option.label}</span>
                  </button>
                );
              })
            )}
          </div>
        </div>,
        document.body,
      )
    : null;

  return (
    <div ref={wrapperRef} className={cn("relative w-full", className)}>
      <input
        ref={inputRef}
        type="text"
        value={inputDisplayValue}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-haspopup="listbox"
        className="h-10 w-full rounded-lg border border-border bg-background px-4 pr-10 text-sm text-foreground outline-none transition-all placeholder:text-muted-foreground focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:bg-muted"
        onFocus={() => {
          openDropdown();
          requestAnimationFrame(() => {
            const inputElement = inputRef.current;
            if (inputElement) {
              inputElement.setSelectionRange(0, inputElement.value.length);
            }
          });
        }}
        onClick={() => {
          if (!open) {
            openDropdown();
          }
        }}
        onChange={handleInputChange}
        onKeyDown={handleInputKeyDown}
      />
      <button
        type="button"
        aria-label="Toggle department dropdown"
        tabIndex={-1}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground"
        onMouseDown={(event) => {
          event.preventDefault();
          if (open) {
            closeDropdown();
          } else {
            openDropdown();
            requestAnimationFrame(() => inputRef.current?.focus());
          }
        }}
      >
        <ChevronDownIcon className={cn("size-4 transition-transform", open && "rotate-180")} />
      </button>
      {dropdown}
    </div>
  );
}

export { Combobox };