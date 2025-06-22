'use client'

import { forwardRef } from 'react'
import { SlugInput, type SlugInputProps } from '@/components/ui/SlugInput'
import type { ChangeHandler } from 'react-hook-form'

interface OrgSlugInputProps extends Omit<SlugInputProps, 'prefix' | 'label' | 'onChange' | 'sourceValue'> {
  name: string
  onChange?: ChangeHandler
  onBlur?: ChangeHandler
}

export const OrgSlugInput = forwardRef<HTMLInputElement, OrgSlugInputProps>(
  ({ name: sourceValue, onChange, onBlur, ...props }, ref) => {
    return (
      <SlugInput
        ref={ref}
        label="Organization URL"
        prefix="orgs"
        sourceValue={sourceValue}
        placeholder="your-org-name"
        autoGenerate={true}
        className="bg-background"
        onChange={(value) => {
          onChange?.({
            target: { value },
            type: 'change'
          } as React.ChangeEvent<HTMLInputElement>)
        }}
        onBlur={onBlur}
        {...props}
      />
    )
  }
)

OrgSlugInput.displayName = 'OrgSlugInput' 