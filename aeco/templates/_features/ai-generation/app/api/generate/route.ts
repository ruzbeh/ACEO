import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { createPrediction, waitForPrediction } from "@/lib/ai-client";

export async function POST(request: NextRequest) {
  try {
    const supabase = createRouteHandlerClient({ cookies });
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const formData = await request.formData();
    const image = formData.get("image") as File | null;
    const style = (formData.get("style") as string) || "default";

    if (!image) {
      return NextResponse.json(
        { error: "No image provided" },
        { status: 400 }
      );
    }

    // Convert file to base64 data URI for the API
    const bytes = await image.arrayBuffer();
    const base64 = Buffer.from(bytes).toString("base64");
    const dataUri = `data:${image.type};base64,${base64}`;

    // Create prediction with Replicate
    const model = process.env.REPLICATE_MODEL_ID || "stability-ai/sdxl";
    const prediction = await createPrediction(model, {
      image: dataUri,
      style,
      num_outputs: 4,
    });

    // Poll until complete
    const result = await waitForPrediction(prediction.id);

    if (result.status === "failed") {
      return NextResponse.json(
        { error: result.error || "Generation failed" },
        { status: 500 }
      );
    }

    const imageUrls: string[] = Array.isArray(result.output)
      ? result.output
      : [result.output];

    return NextResponse.json({ imageUrls });
  } catch (error) {
    console.error("Generate route error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
