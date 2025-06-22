'use client'

import { useState, useCallback } from 'react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/dashboard/profile/Avatar'
import { Button } from '@/components/ui/Button'
import { User, Upload } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { Progress } from '@/components/ui/Progress'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/Dialog'
import Cropper from 'react-easy-crop'
import { cn } from '@/utils/cn'
import { toast } from 'sonner'
import { cropImage, type CropArea } from '@/lib/profile/cropService'
import type { ProfileResponse } from '@/lib/auth/authTypes'

interface AvatarUploadState {
  preview: string | null
  progress: number
  state: 'idle' | 'processing' | 'uploading' | 'complete' | 'error'
}

interface CropState {
  imageSrc: string | null
  crop: { x: number; y: number }
  zoom: number
  aspect: number
  croppedAreaPixels: CropArea | null
}

const AVATAR_CONFIG = {
  maxSizeMB: 5,
  maxWidthOrHeight: 1024,
  acceptedTypes: {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/webp': ['.webp']
  }
} as const

// Add new type for context
type AvatarContext = {
  type: 'user' | 'organization'
  id: string
}

interface AvatarUploadProps {
  context: AvatarContext
  currentAvatar: string | null
  onUploadComplete?: (url: string | null) => void
  isFormSubmitting?: boolean
}

export function AvatarUpload({ 
  context,
  currentAvatar, 
  onUploadComplete,
  isFormSubmitting = false 
}: AvatarUploadProps) {
  const [uploadState, setUploadState] = useState<AvatarUploadState>({
    preview: currentAvatar,
    progress: 0,
    state: 'idle'
  })

  const [cropState, setCropState] = useState<CropState>({
    imageSrc: null,
    crop: { x: 0, y: 0 },
    zoom: 1,
    aspect: 1,
    croppedAreaPixels: null
  })

  const [showCropper, setShowCropper] = useState(false)

  const handleCropCancel = useCallback(() => {
    if (cropState.imageSrc) {
      URL.revokeObjectURL(cropState.imageSrc)
    }
    setCropState((prev: CropState) => ({ ...prev, imageSrc: null }))
    setShowCropper(false)
  }, [cropState.imageSrc])

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return
    
    try {
      if (file.size > AVATAR_CONFIG.maxSizeMB * 1024 * 1024) {
        throw new Error(`File size must be less than ${AVATAR_CONFIG.maxSizeMB}MB`)
      }

      const objectUrl = URL.createObjectURL(file)
      setCropState((prev: CropState) => ({ ...prev, imageSrc: objectUrl }))
      setShowCropper(true)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to prepare image')
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: AVATAR_CONFIG.acceptedTypes,
    maxSize: AVATAR_CONFIG.maxSizeMB * 1024 * 1024,
    onDrop: onDrop
  })

  const onCropComplete = useCallback((_croppedArea: CropArea, croppedAreaPixels: CropArea) => {
    setCropState((prev: CropState) => ({ ...prev, croppedAreaPixels }))
  }, [])

  const handleCropSave = async () => {
    const { imageSrc, croppedAreaPixels } = cropState
    if (!imageSrc || !croppedAreaPixels) return

    setShowCropper(false)
    setUploadState((prev: AvatarUploadState) => ({ ...prev, state: 'processing' }))
    
    try {
      const croppedBlob = await cropImage(imageSrc, croppedAreaPixels)
      const formData = new FormData()
      formData.append('file', croppedBlob)
      formData.append('context', JSON.stringify({
        type: context.type,
        id: context.id
      }))

      setUploadState((prev: AvatarUploadState) => ({ 
        ...prev, 
        state: 'uploading' 
      }))

      const endpoint = context.type === 'organization' 
        ? '/api/orgs/avatar'
        : '/api/profile/avatar'

      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
        }
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.message || 'Upload failed')
      }
      
      const result = await response.json() as ProfileResponse
      if (result.error) {
        throw result.error
      }

      const avatarUrl = result.data?.avatar_url || null
      if (!avatarUrl) {
        throw new Error('No avatar URL returned')
      }

      setUploadState({
        preview: avatarUrl,
        progress: 100,
        state: 'complete'
      })

      onUploadComplete?.(avatarUrl)
      
    } catch (error) {
      console.error('Failed to process image:', error)
      setUploadState((prev: AvatarUploadState) => ({
        ...prev,
        state: 'error',
        preview: currentAvatar
      }))
      toast.error(error instanceof Error ? error.message : 'Failed to upload avatar')
    } finally {
      if (cropState.imageSrc) {
        URL.revokeObjectURL(cropState.imageSrc)
      }
      setCropState((prev: CropState) => ({ ...prev, imageSrc: null }))
    }
  }

  const handleRemove = async () => {
    try {
      const endpoint = context.type === 'organization'
        ? `/api/orgs/avatar?orgId=${context.id}`
        : `/api/profile/avatar?userId=${context.id}`

      const response = await fetch(endpoint, {
        method: 'DELETE',
        credentials: 'same-origin'
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Failed to remove avatar')
      }

      setUploadState({
        preview: null,
        progress: 0,
        state: 'idle'
      })
      onUploadComplete?.(null)
    } catch (error) {
      console.error('Avatar removal failed:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to remove avatar')
    }
  }

  // JSX remains mostly the same but uses new state structure
  return (
    <div className="flex flex-col items-center gap-4">
      <div 
        {...getRootProps()} 
        className={cn(
          "relative cursor-pointer rounded-full transition-colors",
          isDragActive && "ring-2 ring-primary"
        )}
      >
        <Avatar className="h-24 w-24">
          {uploadState.preview ? (
            <AvatarImage src={uploadState.preview} />
          ) : (
            <AvatarFallback>
              {isDragActive ? (
                <Upload className="h-12 w-12 animate-pulse text-muted-foreground" />
              ) : (
                <User className="h-12 w-12 text-muted-foreground" />
              )}
            </AvatarFallback>
          )}
        </Avatar>
        <input {...getInputProps()} id="avatar-upload" />
      </div>

      {uploadState.state === 'uploading' && (
        <div className="w-full max-w-[200px]">
          <Progress value={uploadState.progress} className="h-1" />
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button 
          variant="outline"
          size="md"
          disabled={isFormSubmitting || uploadState.state === 'uploading'}
          onClick={(e) => {
            e.stopPropagation()
            document.getElementById('avatar-upload')?.click()
          }}
        >
          Change Avatar
        </Button>
        {uploadState.preview && (
          <Button 
            variant="ghost"
            size="md"
            onClick={handleRemove}
            disabled={isFormSubmitting || uploadState.state === 'uploading'}
          >
            Remove
          </Button>
        )}
      </div>

      <Dialog 
        open={showCropper} 
        onOpenChange={(open) => {
          if (!open) handleCropCancel()
          setShowCropper(open)
        }}
      >
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle className="text-foreground">Crop Avatar</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Adjust the crop area to select your profile avatar image.
            </DialogDescription>
          </DialogHeader>

          <div className="relative h-[450px] w-full bg-background">
            <Cropper
              image={cropState.imageSrc || ''}
              crop={cropState.crop}
              zoom={cropState.zoom}
              aspect={cropState.aspect}
              onCropChange={(crop) => setCropState(prev => ({ ...prev, crop }))}
              onZoomChange={(zoom) => setCropState(prev => ({ ...prev, zoom }))}
              onCropComplete={onCropComplete}
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button 
              variant="ghost"
              size="md"
              onClick={handleCropCancel}
            >
              Cancel
            </Button>
            <Button 
              variant="primary"
              size="md"
              onClick={handleCropSave}
            >
              Apply
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}