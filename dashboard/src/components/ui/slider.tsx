"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface SliderProps {
  value?: number;
  min?: number;
  max?: number;
  step?: number;
  onChange?: (value: number) => void;
  className?: string;
  trackColor?: string;
  fillColor?: string;
}

export function Slider({
  value = 0,
  min = 0,
  max = 100,
  step = 1,
  onChange,
  className,
  trackColor = "bg-gray-200",
  fillColor = "bg-primary",
}: SliderProps) {
  const [localValue, setLocalValue] = React.useState(value);
  const [isDragging, setIsDragging] = React.useState(false);

  const percentage = ((localValue - min) / (max - min)) * 100;

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    updateValue(e);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      updateValue(e);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const updateValue = (e: React.MouseEvent) => {
    const slider = e.currentTarget as HTMLElement;
    const rect = slider.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, x / rect.width));
    const newValue = min + percentage * (max - min);
    const steppedValue = Math.round(newValue / step) * step;
    const clampedValue = Math.max(min, Math.min(max, steppedValue));
    setLocalValue(clampedValue);
    onChange?.(clampedValue);
  };

  React.useEffect(() => {
    if (isDragging) {
      const handleGlobalMouseMove = (e: MouseEvent) => {
        const slider = document.querySelector("[data-slider]") as HTMLElement;
        if (slider) {
          const rect = slider.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const pct = Math.max(0, Math.min(1, x / rect.width));
          const newValue = min + pct * (max - min);
          const steppedValue = Math.round(newValue / step) * step;
          const clampedValue = Math.max(min, Math.min(max, steppedValue));
          setLocalValue(clampedValue);
          onChange?.(clampedValue);
        }
      };

      const handleGlobalMouseUp = () => {
        setIsDragging(false);
      };

      document.addEventListener("mousemove", handleGlobalMouseMove);
      document.addEventListener("mouseup", handleGlobalMouseUp);

      return () => {
        document.removeEventListener("mousemove", handleGlobalMouseMove);
        document.removeEventListener("mouseup", handleGlobalMouseUp);
      };
    }
  }, [isDragging, min, max, step, onChange]);

  return (
    <div
      data-slider
      className={cn("relative w-full h-6 flex items-center cursor-pointer", className)}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <div className={cn("relative w-full h-2 rounded-full", trackColor)}>
        <div
          className={cn("absolute h-full rounded-full", fillColor)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div
        className="absolute w-5 h-5 bg-white border-2 border-primary rounded-full shadow-md transform -translate-x-1/2"
        style={{ left: `${percentage}%` }}
      />
    </div>
  );
}