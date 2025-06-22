import { createImage } from "./imageProcessing"

export interface Point {
  x: number
  y: number
}

export interface CropArea {
  width: number
  height: number
  x: number
  y: number
}

export async function cropImage(
  imageUrl: string, 
  cropArea: CropArea,
  quality: number = 0.9
): Promise<Blob> {
  try {
    const image = await createImage(imageUrl)
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    
    if (!ctx) {
      throw new Error('Failed to get canvas context')
    }

    canvas.width = cropArea.width
    canvas.height = cropArea.height

    // Draw the cropped image
    ctx.drawImage(
      image,
      cropArea.x,
      cropArea.y,
      cropArea.width,
      cropArea.height,
      0,
      0,
      cropArea.width,
      cropArea.height
    )

    // Convert to blob
    return new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve(blob)
          } else {
            reject(new Error('Failed to create blob from canvas'))
          }
        },
        'image/jpeg',
        quality
      )
    })
  } catch (error) {
    console.error('Failed to crop image:', error)
    throw error
  }
}