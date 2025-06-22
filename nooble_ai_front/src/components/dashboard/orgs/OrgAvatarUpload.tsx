'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { OrgAvatar, OrgAvatarFallback, OrgAvatarImage } from './OrgAvatar'
import { Button } from '@/components/ui/Button'
import { Building2, Upload } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { Progress } from '@/components/ui/Progress'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/Dialog'
import Cropper from 'react-easy-crop'
import { cn } from '@/utils/cn'
import { toast } from 'sonner'
import { cropImage, type CropArea } from '@/lib/profile/cropService'
import type { Organization } from '@/lib/orgs/orgTypes'

interface OrgAvatarUploadState {
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

interface OrgAvatarUploadProps {
  orgId: string
  currentAvatar: string | null
  onUploadComplete?: (url: string | null) => void
  isFormSubmitting?: boolean
}

export function OrgAvatarUpload({ 
  orgId,
  currentAvatar, 
  onUploadComplete,
  isFormSubmitting = false 
}: OrgAvatarUploadProps) {
  const router = useRouter()

  const [uploadState, setUploadState] = useState<OrgAvatarUploadState>({
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
    setCropState(prev => ({ ...prev, imageSrc: null }))
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
      setCropState(prev => ({ ...prev, imageSrc: objectUrl }))
      setShowCropper(true)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to prepare image')
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: AVATAR_CONFIG.acceptedTypes,
    maxSize: AVATAR_CONFIG.maxSizeMB * 1024 * 1024,
    multiple: false,
    disabled: showCropper
  })

  const onCropComplete = useCallback((_croppedArea: CropArea, croppedAreaPixels: CropArea) => {
    setCropState(prev => ({ ...prev, croppedAreaPixels }))
  }, [])

  const handleCropSave = async () => {
    const { imageSrc, croppedAreaPixels } = cropState
    if (!imageSrc || !croppedAreaPixels) return

    setShowCropper(false)
    setUploadState(prev => ({ ...prev, state: 'processing' }))
    
    try {
      const croppedBlob = await cropImage(imageSrc, croppedAreaPixels)
      const formData = new FormData()
      formData.append('file', croppedBlob, 'avatar.jpg')
      formData.append('orgId', orgId)

      setUploadState(prev => ({ ...prev, state: 'uploading' }))

      const response = await fetch('/api/orgs/orgavatar', {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: {
          'Accept': 'application/json'
        }
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error?.message || 'Upload failed')
      }

      const result = await response.json() as { data: Organization | null, error: Error | null }
      if (result.error) throw result.error
      if (!result.data?.avatar_url) throw new Error('No avatar URL returned')

      const refreshedUrl = `${result.data.avatar_url}?t=${Date.now()}`
      
      setUploadState({
        preview: refreshedUrl,
        progress: 100,
        state: 'complete'
      })
      
      onUploadComplete?.(refreshedUrl)
      
      router.refresh()

    } catch (error) {
      console.error('Failed to process image:', error)
      setUploadState(prev => ({
        ...prev,
        state: 'error',
        preview: currentAvatar
      }))
      
      const message = error instanceof Error 
        ? error.message
        : typeof error === 'object' && error && 'message' in error
        ? String(error.message)
        : 'Failed to upload avatar'
        
      toast.error(message)
    } finally {
      if (cropState.imageSrc) {
        URL.revokeObjectURL(cropState.imageSrc)
      }
      setCropState(prev => ({ 
        ...prev, 
        imageSrc: null,
        croppedAreaPixels: null
      }))
    }
  }

  const handleRemove = async (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    
    try {
      const response = await fetch(`/api/orgs/orgavatar?orgId=${orgId}`, {
        method: 'DELETE',
        credentials: 'same-origin'
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error?.message || 'Failed to remove avatar')
      }

      window.location.reload()
      
    } catch (error) {
      console.error('Avatar removal failed:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to remove avatar')
    }
  }

  return (
    <div 
      {...getRootProps()}
      className={cn(
        "flex flex-col items-center gap-4 rounded-lg p-4 transition-colors border border-border",
        isDragActive && "bg-muted",
        (uploadState.state === 'uploading' || uploadState.state === 'processing' || showCropper) && 
          "pointer-events-none opacity-50"
      )}
    >
      <div className="cursor-pointer">
        <OrgAvatar 
          className="h-24 w-24"
          organization={{
            id: orgId,
            name: 'Preview',
            slug: 'preview',
            avatar_url: uploadState.preview || undefined,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }}
        >
          {uploadState.preview ? (
            <OrgAvatarImage 
              src={uploadState.preview} 
              data-refresh={true}
            />
          ) : (
            <OrgAvatarFallback>
              {isDragActive ? (
                <Upload className="h-12 w-12 animate-pulse text-muted-foreground" />
              ) : (
                <Building2 className="h-12 w-12 text-muted-foreground" />
              )}
            </OrgAvatarFallback>
          )}
        </OrgAvatar>
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
          isLoading={uploadState.state === 'uploading'}
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
            isLoading={uploadState.state === 'uploading'}
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
              Adjust the crop area to select your organization avatar image.
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
              isLoading={uploadState.state === 'processing'}
            >
              Cancel
            </Button>
            <Button 
              variant="primary"
              size="md"
              onClick={handleCropSave}
              isLoading={uploadState.state === 'processing'}
            >
              Apply
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

