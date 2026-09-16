import Foundation
import Vision
import ImageIO
import CoreImage
import AppKit

let input = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
let source = CGImageSourceCreateWithURL(input as CFURL, nil)!
let image = CGImageSourceCreateImageAtIndex(source, 0, nil)!
let width = image.width, height = image.height
func box(_ r: CGRect) -> [Double] {
    [Double(r.minX) * Double(width), (1-Double(r.maxY))*Double(height), Double(r.maxX)*Double(width), (1-Double(r.minY))*Double(height)]
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["pt-BR", "en-US"]
request.usesLanguageCorrection = true
let handler = VNImageRequestHandler(cgImage: image, options: [:])
try handler.perform([request])
var rows: [[String:Any]] = []
for (index, observation) in (request.results ?? []).enumerated() {
    guard let text = observation.topCandidates(1).first else {continue}
    var words: [[String:Any]] = []
    text.string.enumerateSubstrings(in: text.string.startIndex..<text.string.endIndex, options:.byWords) { substring,range,_,_ in
        if let bounds = try? text.boundingBox(for:range) {
            words.append(["text":substring ?? "", "bbox_px":box(bounds.boundingBox)])
        }
    }
    rows.append(["id":"ocr_\(index)","text":text.string,"confidence":text.confidence,"bbox_px":box(observation.boundingBox),"words":words])
}
var result: [String:Any] = ["engine":"Apple Vision local", "width":width, "height":height, "elements":rows]
if #available(macOS 14.0, *) {
    do {
        let segmentation = VNGenerateForegroundInstanceMaskRequest()
        try handler.perform([segmentation])
        if let observation = segmentation.results?.first, !observation.allInstances.isEmpty {
            let buffer = try observation.generateScaledMaskForImage(forInstances:observation.allInstances, from:handler)
            let ci = CIImage(cvPixelBuffer:buffer)
            let cg = CIContext().createCGImage(ci, from:ci.extent)!
            let bitmap = NSBitmapImageRep(cgImage:cg)
            try bitmap.representation(using:.png, properties:[:])!.write(to:output.appendingPathComponent("foreground-mask.png"))
            result["foreground_mask"]="foreground-mask.png"
            result["foreground_instances"]=observation.allInstances.count
        } else { result["segmentation_status"]="no_instances" }
    } catch { result["segmentation_error"]=String(describing:error) }
}
let json = try JSONSerialization.data(withJSONObject:result, options:[.prettyPrinted,.sortedKeys])
try json.write(to:output.appendingPathComponent("ocr.json"))
print(String(data:json,encoding:.utf8)!)
